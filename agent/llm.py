"""Minimal Ollama client (Python standard library only, talks to the LOCAL Ollama server).

No cloud API is used anywhere. The default host is http://127.0.0.1:11434.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)


class LLMError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, model, host=None, logger=None, keep_alive="30m"):
        self.host = (host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self.model = model
        self.logger = logger
        self.keep_alive = keep_alive
        self.calls = 0
        self._think_supported = True
        self.tok_s = None            # measured generation speed (tokens / second)
        self.last_truncated = False

    # ---------------------------------------------------------------- HTTP
    def _post(self, path, payload, timeout):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.host + path, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            raise LLMError(f"HTTP {e.code}: {body[:300]}")
        except Exception as e:  # timeout, connection refused, ...
            raise LLMError(f"{type(e).__name__}: {e}")

    def _get(self, path, timeout=10):
        try:
            with urllib.request.urlopen(self.host + path, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            raise LLMError(f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------- models
    def resolve_model(self):
        """Use only the requested model; never silently switch models."""
        tags = self._get("/api/tags")
        names = [m.get("name", "") for m in tags.get("models", [])]
        if not names:
            raise LLMError("No model is installed in Ollama. Run: ollama pull <model>")
        want = self.model
        for n in names:
            if n == want or n == want + ":latest" or n.split(":")[0] == want:
                self.model = n
                return n
        raise LLMError(
            f"Required model '{want}' is not installed. "
            f"Run: ollama pull {want}. "
            f"Installed models: {names}"
        )

    # --------------------------------------------------------------- chat
    def _stream(self, payload, deadline):
        """Streamed /api/chat with a hard wall-clock deadline.
        Closing the connection makes Ollama STOP generating, so an over-long call never keeps
        the model busy in the background (that used to make the next calls time out too)."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.host + "/api/chat", data=data,
                                     headers={"Content-Type": "application/json"})
        content, thinking, info = [], [], {"truncated": False, "chunks": 0}
        try:
            resp = urllib.request.urlopen(req, timeout=max(1.0, deadline - time.time()))
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")
        except Exception as e:
            raise LLMError(f"{type(e).__name__}: {e}")
        try:
            for line in resp:
                if not line.strip():
                    continue
                obj = json.loads(line.decode("utf-8"))
                if obj.get("error"):
                    raise LLMError(str(obj["error"])[:300])
                msg = obj.get("message") or {}
                content.append(msg.get("content") or "")
                thinking.append(msg.get("thinking") or "")
                info["chunks"] += 1
                if obj.get("done"):
                    info.update(done_reason=obj.get("done_reason"), eval_count=obj.get("eval_count"),
                                eval_duration=obj.get("eval_duration"),
                                load_duration=obj.get("load_duration"))
                    break
                if time.time() > deadline:
                    info["truncated"] = True
                    break
        except LLMError:
            raise
        except Exception:            # socket timeout while waiting -> treat as truncated
            info["truncated"] = True
        finally:
            try:
                resp.close()
            except Exception:
                pass
        return "".join(content), "".join(thinking), info

    def _update_speed(self, info, seconds):
        if info.get("eval_count") and info.get("eval_duration"):
            tps = info["eval_count"] / (info["eval_duration"] / 1e9)
        elif info.get("chunks", 0) > 20 and seconds > 0:
            tps = info["chunks"] / seconds          # lower bound (includes prompt processing)
        else:
            return
        self.tok_s = tps if self.tok_s is None else 0.5 * self.tok_s + 0.5 * tps

    def warmup(self, timeout=900):
        """Load the model into memory (can take minutes for big models) and measure tokens/second.
        Not counted in any problem's time budget."""
        t0 = time.time()
        self.chat([{"role": "user", "content": "Count from 1 to 15 separated by spaces."}],
                  think=False, temperature=0.0, num_predict=40, num_ctx=2048,
                  timeout=timeout, tag="warmup")
        return time.time() - t0

    def chat(self, messages, think=True, temperature=0.6, num_predict=6144,
             num_ctx=8192, timeout=300, tag=""):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "top_p": 0.95,
                "top_k": 20,
                "num_predict": num_predict,
                "num_ctx": num_ctx,
            },
        }
        if self._think_supported:
            payload["think"] = bool(think)
        t0 = time.time()
        deadline = t0 + timeout
        self.calls += 1
        try:
            content, thinking, info = self._stream(payload, deadline)
        except LLMError as e:
            # Older Ollama versions do not know the "think" field -> retry without it.
            if "think" in str(e).lower() and self._think_supported:
                self._think_supported = False
                payload.pop("think", None)
                content, thinking, info = self._stream(payload, deadline)
            else:
                raise
        # Models/versions that inline <think>...</think> in content.
        m = re.search(r"<think>(.*?)(</think>|$)", content, re.S | re.I)
        if m:
            thinking = thinking or m.group(1)
        content = THINK_RE.sub("", content)
        content = re.sub(r"^.*?</think>", "", content, flags=re.S)
        content = re.sub(r"<think>.*$", "", content, flags=re.S)   # cut off while still thinking
        content = content.strip()
        dt = time.time() - t0
        self._update_speed(info, dt)
        self.last_truncated = info["truncated"]
        if self.logger:
            self.logger.log("llm_call", tag=tag, seconds=round(dt, 1), think=think,
                            temperature=temperature, messages=messages,
                            thinking=thinking[-4000:], content=content,
                            done_reason=info.get("done_reason") or ("time_cap" if info["truncated"] else None),
                            eval_count=info.get("eval_count") or info["chunks"],
                            tok_s=round(self.tok_s, 1) if self.tok_s else None)
        return content, thinking
