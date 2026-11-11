"""The reasoning agent.

Pipeline per problem (adaptive, budgeted):
  0. Analyzer       : infer the output contract (format) from the problem text  [no LLM call]
  0b. Knowledge    : Persian digits -> ASCII, glossary for Persian calendar words   [no LLM call]
  1. PoT / ReAct    : LLM writes a Python program -> run it in a sandbox -> observation is fed
                      back (errors, timeouts, wrong format, >1 solutions) -> LLM revises (reflection)
  2. CoT            : independent natural-language chain-of-thought solution
  3. Early exit     : if the two independent paths agree -> done (2 calls)
  4. Self-consistency: otherwise sample one more of each path and vote (weighted)
  5. Verifier/Judge : if candidates still disagree, a critic checks every candidate
                      against every condition and picks one
  6. Formatter      : deterministic normalisation into the exact required format
"""
import re
import time
from collections import OrderedDict

from . import prompts
from .knowledge import augment
from .formatter import analyze, finalize, format_hint, is_valid, same
from .llm import LLMError
from .sandbox import extract_code, hardcoded_answer, parse_program_output, run_python

MIN_CALL_SECONDS = 10
FINAL_RE = re.compile(r"(?im)^[\s*#>`]*(final\s*answer|پاسخ\s*نهایی)\s*\**\s*[:：=]")
CONCISE = ("\n\nTime is limited: keep your reasoning SHORT (at most ~150 words), then write the "
           "FINAL ANSWER line.")


def has_final(text):
    """A reasoning answer counts only if the model actually reached its FINAL ANSWER line
    (a reply cut off mid-sentence must never be mined for a random number or letter)."""
    return bool(text) and bool(FINAL_RE.search(text))


class Agent:
    def __init__(self, llm, logger, budget_s=300, max_calls=8, think=True, pot_think=False,
                 code_timeout=15, max_fixes=2, num_ctx=8192, cot_predict=6144, pot_predict=2048):
        self.llm = llm
        self.log = logger
        self.budget_s = budget_s
        self.max_calls = max_calls
        self.think = think                 # thinking for CoT / judge
        self.pot_think = pot_think and think
        self.code_timeout = code_timeout
        self.max_fixes = max_fixes
        self.num_ctx = num_ctx
        self.cot_predict = cot_predict
        self.pot_predict = cot_predict if self.pot_think else pot_predict

    # ------------------------------------------------------------ helpers
    def _left(self, until=None):
        return (until or self.deadline) - time.time()

    def _soft_deadline(self):
        """Normal calls stop here; the rest of the budget is reserved for a last-resort answer."""
        return self.deadline - self.reserve

    def _can_call(self, until=None):
        until = min(until or self._soft_deadline(), self._soft_deadline())
        return self.calls < self.max_calls and self._left(until) > MIN_CALL_SECONDS

    def _think_ok(self, until=None):
        """Use thinking only if the measured speed allows ~2500 tokens in the remaining time.
        On slow hardware (e.g. a 27B model partly on CPU) thinking would just time out."""
        if not self.think:
            return False
        tps = self.llm.tok_s
        until = min(until or self._soft_deadline(), self._soft_deadline())
        return tps is None or tps * self._left(until) >= 2500

    def _enough(self, until, tokens):
        """Is there time to generate about `tokens` more tokens before `until`?"""
        tps = self.llm.tok_s
        until = min(until or self._soft_deadline(), self._soft_deadline())
        return tps is None or tps * self._left(until) >= tokens

    def _chat(self, messages, temperature, tag, think, num_predict, until=None, final=False):
        until = self.deadline if final else min(until or self._soft_deadline(), self._soft_deadline())
        if not final and not self._can_call(until):
            raise LLMError("budget exhausted")
        self.calls += 1
        return self.llm.chat(messages, think=think, temperature=temperature, num_predict=num_predict,
                             num_ctx=self.num_ctx, timeout=max(MIN_CALL_SECONDS, self._left(until)),
                             tag=f"{self.pid}:{tag}")

    # ------------------------------------------------- path 1: PoT + ReAct
    def program_of_thought(self, temperature, time_cap, think=None):
        until = time.time() + time_cap          # leave time for the other reasoning path
        think = self.pot_think if think is None else (think and self.think)
        think = think and self._think_ok(until)
        num_predict = self.cot_predict if think else self.pot_predict
        msgs = [{"role": "system", "content": prompts.POT_SYSTEM},
                {"role": "user", "content": prompts.POT_USER.format(problem=self.problem, hint=self.hint)}]
        fallback = None
        reflected = False
        seen_code = set()
        for step in range(1 + self.max_fixes):
            try:
                content, thinking = self._chat(msgs, temperature, f"pot{step}", think, num_predict, until)
            except LLMError as e:
                self.log.warn(f"[{self.pid}] PoT stopped: {e}")
                break
            code = extract_code(content) or extract_code(thinking)
            key = re.sub(r"\s+", " ", code).strip()
            if key and key in seen_code:
                # ReAct's most frequent failure mode: repeating the previous action instead of using
                # the observation. Re-running identical code cannot change anything -> stop the loop.
                self.log.log("tool_run", pid=self.pid, step=step, repeated=True)
                self.log.warn(f"[{self.pid}] PoT repeated the same program; stopping the loop")
                break
            seen_code.add(key)
            ok, out, err = run_python(code, timeout=self.code_timeout)
            raw, nsol = parse_program_output(out) if ok else (None, None)
            ans = finalize(raw, self.spec) if raw else ""
            self.log.log("tool_run", pid=self.pid, step=step, code=code, ok=ok, stdout=out[-1500:],
                         stderr=err[-1500:], parsed=raw, nsol=nsol, answer=ans)
            last = step == self.max_fixes
            literal = bool(code) and hardcoded_answer(code)

            if ok and literal and not last and self._enough(until, 450):
                fallback = fallback or (ans if is_valid(ans, self.spec) else None)
                obs = out[-1500:] or "(no output)"
                instr = ("Your program prints a HARD-CODED literal answer instead of computing it. Rewrite it so the "
                         "answer is computed from the constraints/data and printed from a variable, e.g.\n"
                         "print('NUM_SOLUTIONS:', len(solutions))\nprint('ANSWER:', answer)")
            elif ok and is_valid(ans, self.spec) and nsol != 0:
                if nsol is not None and nsol > 1 and not reflected and not last and self._enough(until, 450):
                    fallback = fallback or ans
                    reflected = True
                    obs = out[-1500:]
                    instr = (f"Your program reports NUM_SOLUTIONS={nsol}, but the question expects exactly ONE answer. "
                             "You most likely missed or mis-encoded a condition, or misread what is asked. "
                             "Re-read the ORIGINAL problem text word by word, check every constraint in your code, "
                             "and fix the program.")
                else:
                    weight = 1.0 if (nsol is None or nsol == 1) else 0.5
                    if literal:
                        weight = 0.5
                    return ans, weight
            elif ok and nsol == 0:
                obs = out[-1500:]
                instr = ("Your program found NO solution, but the problem has one. A constraint is mis-encoded "
                         "or too strict (check directions like before/after, off-by-one, and domains). "
                         "Re-read the ORIGINAL problem and fix the program.")
            elif ok and not out.strip():
                obs = "(the program printed nothing)"
                instr = ("Your program printed nothing. Use top-level code (do not only define functions) and end with\n"
                         "print('NUM_SOLUTIONS:', n)\nprint('ANSWER:', answer)")
            elif ok:
                obs = out[-1500:]
                instr = (f"The printed ANSWER is missing or not in the required format. {self.hint}\n"
                         "The program must end by printing 'NUM_SOLUTIONS: <k>' and 'ANSWER: <answer>'.")
            else:
                obs = (err or out or "error")[-1500:]
                instr = "The program failed. Fix the bug (standard library only, must finish in a few seconds)."
            msgs.append({"role": "assistant", "content": f"```python\n{code}\n```" if code else content[-3000:]})
            msgs.append({"role": "user", "content": prompts.POT_OBSERVATION.format(observation=obs, instruction=instr)})
        return (fallback, 0.5) if fallback else (None, 0)

    # ------------------------------------------------------ path 2: CoT
    def chain_of_thought(self, temperature):
        think = self._think_ok()
        user = prompts.COT_USER.format(problem=self.problem, hint=self.hint) + ("" if think else CONCISE)
        msgs = [{"role": "system", "content": prompts.COT_SYSTEM}, {"role": "user", "content": user}]
        try:
            content, thinking = self._chat(msgs, temperature, "cot", think,
                                           self.cot_predict if think else min(2048, self.cot_predict))
        except LLMError as e:
            self.log.warn(f"[{self.pid}] CoT stopped: {e}")
            self.cot_failed += 1
            return None, 0
        ans = finalize(content, self.spec) if has_final(content) else ""
        if is_valid(ans, self.spec):
            return ans, 1.0
        self.cot_failed += 1
        tail = thinking[-400:] if thinking else ""
        if has_final(tail):                         # output cut off while thinking -> weak vote
            ans = finalize(tail, self.spec)
            if is_valid(ans, self.spec):
                return ans, 0.4
        return None, 0

    # ----------------------------------------------------- verifier/judge
    def judge(self, tally):
        cands = "\n".join(f"- {a}   (x{len(v['sources'])}, from {', '.join(v['sources'])})" for a, v in tally.items())
        msgs = [{"role": "system", "content": prompts.JUDGE_SYSTEM},
                {"role": "user", "content": prompts.JUDGE_USER.format(problem=self.problem, hint=self.hint,
                                                                    candidates=cands)}]
        think = self._think_ok()
        if not think:
            msgs[-1]["content"] += CONCISE
        try:
            content, thinking = self._chat(msgs, 0.3, "judge", think,
                                           self.cot_predict if think else min(2048, self.cot_predict))
        except LLMError as e:
            self.log.warn(f"[{self.pid}] judge stopped: {e}")
            return None
        ans = finalize(content, self.spec) if has_final(content) else ""
        return ans if is_valid(ans, self.spec) else None

    # --------------------------------------------------------- voting
    def _tally(self):
        t = OrderedDict()
        for ans, src, w in self.votes:
            key = next((k for k in t if same(k, ans)), ans)
            e = t.setdefault(key, {"w": 0.0, "sources": []})
            e["w"] += w
            e["sources"].append(src)
        return OrderedDict(sorted(t.items(), key=lambda kv: (-kv[1]["w"], -len(kv[1]["sources"]))))

    def _add(self, ans, w, src):
        if ans:
            self.votes.append((ans, src, w))

    # ----------------------------------------------------------- main
    def solve(self, pid, problem):
        self.pid = pid
        self.spec = analyze(problem)
        self.hint = format_hint(self.spec)
        self.problem = augment(problem)
        self.deadline = time.time() + self.budget_s
        self.reserve = max(20.0, 0.12 * self.budget_s)
        self.calls = 0
        self.votes = []
        self.cot_failed = 0
        self.log.log("start", pid=pid, spec=self.spec)
        self.log.info(f"[{pid}] solving... (format: {self.spec['kind']})")

        # Round 1: two independent reasoning paths (code path may use at most 35% of the budget)
        a, w = self.program_of_thought(0.2, 0.35 * self.budget_s)
        self._add(a, w, "code")
        b, w2 = self.chain_of_thought(0.6)
        self._add(b, w2, "cot")
        if a and b and same(a, b):
            return self._done(a, "agree-r1")

        # Round 2: self-consistency sampling
        if self._can_call():
            # second code sample WITH thinking: slower but stronger and more diverse
            a2, w = self.program_of_thought(0.6, max(MIN_CALL_SECONDS + 1, 0.5 * self._left()), think=True)
            self._add(a2, w, "code")
        if self._can_call() and not self.cot_failed:   # a CoT that ran out of tokens would likely do it again
            b2, w = self.chain_of_thought(0.8)
            self._add(b2, w, "cot")

        tally = self._tally()
        if not tally:
            return self._last_resort()
        items = list(tally.items())
        top, info = items[0]
        if len(items) == 1 or (len(info["sources"]) >= 3 and info["w"] >= 2 * items[1][1]["w"]):
            return self._done(top, "vote")

        # Round 3: verifier
        if self._can_call():
            j = self.judge(tally)
            if j:
                self._add(j, 2.0, "judge")
                tally = self._tally()
        return self._done(next(iter(tally)), "judge+vote")

    def _last_resort(self):
        """No candidate yet: one short direct answer (no thinking) if time allows."""
        try:
            msgs = [{"role": "user", "content": f"{self.problem}\n\n{self.hint}\nReply with the final answer only."}]
            content, _ = self._chat(msgs, 0.2, "direct", False, 64, final=True)
            ans = finalize(content, self.spec)
            if ans:
                return self._done(ans, "last-resort")
        except LLMError as e:
            self.log.warn(f"[{self.pid}] last resort skipped: {e}")
        return self._done("", "failed")

    def _done(self, ans, how):
        self.log.log("final", pid=self.pid, answer=ans, how=how, calls=self.calls,
                     votes=self.votes, seconds=round(self.budget_s - self._left(), 1))
        self.log.info(f"[{self.pid}] -> {ans!r}  ({how}, {self.calls} LLM calls, "
                      f"{self.budget_s - self._left():.0f}s)")
        return ans
