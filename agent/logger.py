import json
import os
import sys
import time


class RunLogger:
    """JSONL trace of every LLM call / tool run / decision (kept for review), plus short console info."""

    def __init__(self, log_dir="logs", verbose=True):
        self.verbose = verbose
        self.path = None
        try:
            os.makedirs(log_dir, exist_ok=True)
            self.path = os.path.join(log_dir, time.strftime("run_%Y%m%d_%H%M%S.jsonl"))
        except OSError:
            pass

    def log(self, event, **kw):
        if not self.path:
            return
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": round(time.time(), 2), "event": event, **kw},
                                   ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def info(self, msg):
        if self.verbose:
            print(msg, file=sys.stderr, flush=True)
        self.log("info", msg=msg)

    def warn(self, msg):
        print("WARNING: " + msg, file=sys.stderr, flush=True)
        self.log("warning", msg=msg)
