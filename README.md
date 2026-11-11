# LLM Agent Assignment 1 — Local Reasoning Agent with Ollama

A reasoning agent for Persian/English logic and math problems that runs **100% locally** on Ollama — no cloud APIs and no third-party Python packages. Instead of sending a problem to the model once, it combines **Program-of-Thought + ReAct** (the model writes Python, a sandbox executes it, and real observations drive reflection), an independent **Chain-of-Thought** path, **adaptive self-consistency**, a **verifier**, Persian-language **knowledge injection**, and a deterministic **output formatter**. It also adapts to hardware speed.

## Installation and usage

```bash
# 1) Install Ollama and pull the evaluation model (before going offline)
ollama pull qwen3.8:27b          # evaluation model (qwen3:8b was also used during development)

# 2) No Python dependencies (standard library only, Python 3.8+)
pip install -r requirements.txt   # intentionally empty

# 3) Run (standard interface)
python main.py --input input.json --output output.json
```

The default model is `qwen3.8:27b`; it can be changed with `--model <name>` or the `AGENT_MODEL` environment variable.
If the requested model is not installed, the agent stops with a clear error. It never silently switches to another model.

| Option | Default | Description |
|---|---|---|
| `--model` | `qwen3.8:27b` | Ollama model name |
| `--host` | `127.0.0.1:11434` | Local Ollama server address |
| `--budget` | `300` | Time budget per problem (seconds) |
| `--max-calls` | `8` | Maximum number of LLM calls per problem |
| `--no-think` | off | Disable the model's thinking mode completely |
| `--pot-think` | off | Also use thinking when writing code (slower) |
| `--num-ctx` | `8192` | Context window; use e.g. 4096 on low RAM/VRAM |
| `--ids` / `--resume` | — | Solve only some ids / continue an interrupted run without re-solving |

The input can be a single `{"id", "problem"}` object, a list of them, or JSON Lines. The output has the same shape as the input, and the `answer` field contains only the final answer.

## Agent architecture

```
problem ─► Analyzer (output-format contract, no LLM call)
            ├─► Knowledge: Persian digits → ASCII, inline weekday translation ("seshanbe" → "seshanbe (Tuesday)")
            │              + glossary of months and terms (small models read "doshanbe" = Monday as Tuesday!)
            │
            ├─► Path 1: Program-of-Thought + ReAct
            │     LLM (no thinking, fast) writes a Python program → runs in a sandbox (tool) → Observation
            │     (error / timeout / empty output / wrong format / NUM_SOLUTIONS = 0 or > 1 /
            │      hard-coded answer instead of a computed one) → reflection and fix (at most 2 times)
            │     This path uses at most 35% of the time budget so the second path always gets time
            │
            ├─► Path 2: Chain-of-Thought with thinking + self-verification
            │
            ├─► If the two independent paths agree → done (only 2 calls)
            ├─► Otherwise self-consistency: a second code sample (with thinking) + a second CoT + weighted voting
            ├─► If they still disagree → a verifier/critic checks every candidate against every constraint
            │
            └─► Deterministic formatter → `answer` in exactly the required format
```

- **ReAct** (Yao et al., 2022): Thought → Action (code execution) → Observation → revision loop.
- **Program-of-Thought / PAL**: exact computation and exhaustive search (permutations, BFS, `Fraction`) instead of mental arithmetic by the model.
- **Self-consistency** with adaptive early stopping to keep the number of calls low.
- The **verifier** is called only when the candidates disagree.
- **Formatter**: converts Persian digits, strips Markdown and prefixes like "Answer:" (also in Persian), matches options/templates (`Nima=<integer>, ...`), and extracts the number / letter / code.

### Robustness
- `output.json` is created at start-up and rewritten atomically after every problem, so it is always valid JSON.
- Model errors, timeouts or an unreachable Ollama server never crash the run; time and the number of calls are bounded per problem.
- **Adapts to hardware speed:** before the first problem the model is loaded once and its generation speed (tokens/s) is measured (outside the problems' budgets).
  Thinking is used only when it fits in the remaining time. Responses are streamed, and when the time cap is reached the connection is closed so that Ollama **actually stops generating** (an abandoned request never keeps the model busy for the next one).
- 12% of each problem's budget is reserved for a quick fallback answer, so no problem is left unanswered.
- Model-generated code runs in a separate process (`python -I`), in a temporary folder, with a timeout; network/system modules are blocked.
- The code contains no answers or identifiers of the sample problems.

## Results

The comparison runs below were done locally with `qwen3:8b` on Ollama 0.40.11 (100% GPU), offline. The run with the evaluation model (`qwen3.8:27b`) is reported at the end of this section.

### Raw model (baseline) vs. agent
The development set contains 24 new, unseen problems of the same kinds as the public set (algebra, ordering, truth-tellers/liars, critical path, BFS/Dijkstra, counting, remainders, template/option/Yes-No formats, and one English problem). The uniqueness of every answer was verified by exhaustive search.

| Method | Accuracy (24 new problems) | LLM calls | Total time |
|---|---|---|---|
| Baseline: one direct call (thinking on) | 21/24 (88%) | 24 | 584 s |
| **Agent (this project)** | **24/24 (100%)** | 69 (avg. 2.9) | 1077 s |

| 10 public problems | **10/10** with the agent (8 solved by agreement of the two independent paths in the first round) |
|---|---|

### Real run with the evaluation model `qwen3.8:27b`
On a machine where the 16 GB model does not fully fit in VRAM (~6.6 tokens/s, with `--budget 900`):

| Public problems | LLM calls | Total time |
|---|---|---|
| **10/10** | 26 (avg. 2.6) | 64 min |

- All 7 single-answer problems were solved by **agreement of the two independent paths in the first round** (2 calls, 2–5.5 minutes each).
- In the 3 multi-answer problems (2, 3, 10) the CoT reasoning hit the token/time limit and was discarded by the `FINAL ANSWER` rule; the answer came from the code path (3 and 10) or the reserved fallback answer (2). In problem 3 the repeated-action guard stopped the loop.

### Baseline errors and the agent component that fixes them
| Raw-model error | Occurrences | Fixed by |
|---|---|---|
| Wrong translation of Persian weekdays ("seshanbe" = Tuesday read as Wednesday) | 2 problems | Knowledge (inline translation) |
| Invalid output format (`$$` instead of a number) | 1 problem | Formatter |

### Error analysis during development (from the logs)
- The code path without thinking sometimes typed the answer by hand (`print("ANSWER: 2")`) or wrote a buggy Dijkstra; in 5 problems the verifier/CoT picked the correct answer → hard-coded-answer detection and a second code sample with thinking were added.
- Manual experiment in `ollama run`: for a scheduling problem the model wrote code with an always-false condition and **made up the output of code it never ran** ("Wednesday"); actually running it printed nothing. This is the main reason the agent really executes code in a sandbox and relies on observations rather than on the model's claims (ReAct).
- A test run with `qwen3.8:27b` on hardware where the model did not fit in VRAM (~6 tokens/s) exposed a bug: a CoT that hit the time cap and was cut mid-sentence became the source of a random number/letter. Now a CoT/verifier answer only gets a vote if it reached the `FINAL ANSWER:` line, and on slow hardware the agent automatically works without thinking and with short reasoning.

### Note on the public problems
Exhaustive search shows that problems 2 (B or C), 3 (2 or 3) and 10 (413 or 431) each have more than one answer consistent with the constraints; in these cases the agent returns one of the valid answers.

## Connection to the course papers

**ReAct** (Yao et al., ICLR 2023 — arXiv:2210.03629)

| Concept in the paper | Implementation in this agent |
|---|---|
| Thought → Action → Observation loop | Thought: restating the problem and listing the constraints (program comments) → Action: running the program in the sandbox → Observation: real output/error, `NUM_SOLUTIONS`, format errors → revision |
| CoT suffers from hallucination (56% of CoT failures on HotpotQA); ReAct relies on external observations | The code path's answer comes from **real execution**, not from the model's claim (in the manual experiment the model invented the output of code it never ran) |
| Combining ReAct and CoT-SC gave the best results (ReAct→CoT-SC and CoT-SC→ReAct) | Two independent paths (code/ReAct and CoT); agreement → early stop; disagreement → more samples and voting; if the code path gives no answer → CoT vote and fallback answer |
| The combinations reached the performance of CoT-SC with 21 samples using only 3–5 samples | 2.9 calls per problem on average (the tie-breaker metric) |
| Common ReAct failure: repeating the previous action and getting stuck in a loop | If the model resubmits the same program, the loop stops; at most 2 fixes plus a time cap |
| Non-informative observations (23% of failures) derail the reasoning | Observations are targeted: "no solution found → a constraint is mis-encoded", "hard-coded answer", "empty output", etc. |

**WebShop** (Yao et al., NeurIPS 2022 — arXiv:2207.01206) is a simulated online-shopping environment for language agents; implementing it is not part of this assignment, but two of its lessons are applied here:
exact automatic evaluation (a programmatic reward / success rate, similar to accuracy with exact matching of `answer`) → the deterministic formatter;
and the largest agent–human gap lies in **choosing the right option** (option score) → for multiple-choice problems the answer is copied verbatim from the list of options.
On WebShop, one-shot ReAct raised the success rate from 29% (IL / IL+RL) to 40%.

## Project structure

```
main.py              Entry point and standard interface
requirements.txt     No external dependencies (Requirments.txt is the same file, using the spelling from the assignment text)
agent/llm.py         Local Ollama client (REST, standard library)
agent/solver.py      Agent logic (PoT/ReAct, CoT, voting, verifier)
agent/prompts.py     Prompts
agent/sandbox.py     Safe code execution (tool)
agent/formatter.py   Output-format analysis and answer normalization
agent/knowledge.py   General Persian glossary (weekdays, months, terms)
data/public_input.json  The 10 public problems in the input format
logs/                JSONL log of every run (all calls, generated code, tool runs, votes)
logs/sample_public_run.jsonl  Full log of a run on the 10 public problems (10/10)
dev/                 Development and evaluation tools (not needed to run the agent):
  baseline.py          Raw model with a single call, for comparison
  make_hidden_like.py  Builds 24 new problems with brute-force-verified unique answers
  hidden_like_input.json / gold_hidden_like.json   Development evaluation set (24 problems)
  tests/eval_public.py Computes the accuracy of an output.json against an answer file
  Modelfile            Custom Ollama model for manually demonstrating the CoT path
```

## Development evaluation (from the repository root)

```bash
python main.py --input dev/hidden_like_input.json --output dev/out_hidden_like.json
python dev/tests/eval_public.py dev/out_hidden_like.json dev/gold_hidden_like.json
python dev/baseline.py --input dev/hidden_like_input.json --output dev/out_baseline.json
python dev/tests/eval_public.py dev/out_baseline.json dev/gold_hidden_like.json
```
