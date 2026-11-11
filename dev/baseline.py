"""Dev-only BASELINE (section 7 of the assignment): send each problem DIRECTLY to the model,
one call, no agent. Compare its accuracy with the agent.

Run from the repository root:
  python dev/baseline.py --input dev/hidden_like_input.json --output dev/out_baseline.json
  python dev/tests/eval_public.py dev/out_baseline.json dev/gold_hidden_like.json
"""
import argparse
import json
import re
import sys
import time
import urllib.request


def ask(host, model, problem, think, timeout):
    payload = {"model": model, "stream": False, "think": think,
               "messages": [{"role": "user", "content": problem + "\n\nReply with the final answer only."}],
               "options": {"temperature": 0.6, "num_ctx": 4096, "num_predict": 6144}}
    req = urllib.request.Request(host + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content = json.loads(r.read())["message"]["content"]
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    return lines[-1] if lines else ""


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--no-think", action="store_true")
    ap.add_argument("--timeout", type=float, default=300)
    a = ap.parse_args()
    host = a.host if a.host.startswith("http") else "http://" + a.host
    data = json.load(open(a.input, encoding="utf-8-sig"))
    items = data if isinstance(data, list) else [data]
    out, t0 = [], time.time()
    for it in items:
        try:
            ans = ask(host, a.model, it["problem"], not a.no_think, a.timeout)
        except Exception as e:
            print(f"[{it['id']}] error: {e}", file=sys.stderr)
            ans = ""
        print(f"[{it['id']}] -> {ans!r}", file=sys.stderr)
        out.append({"id": it["id"], "answer": ans})
        json.dump(out, open(a.output, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"done: {len(out)} problems, {len(out)} LLM calls, {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
