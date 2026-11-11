"""Prompt templates. Generic: nothing here refers to a specific test problem."""

POT_SYSTEM = """You are a meticulous problem solver that solves reasoning problems by WRITING AND RUNNING PYTHON.
Problems may be written in Persian (Farsi); read them carefully.

Method:
1. First, in Python comments, restate the problem: list the unknowns, their domains, and EVERY condition / constraint, one per line. Do not drop any condition.
2. Write a complete, self-contained Python 3 program (standard library only) that computes the answer:
   - logic / ordering / assignment / truth-teller / digit puzzles: enumerate ALL candidates exhaustively (itertools.product / permutations) and keep those that satisfy every constraint;
   - arithmetic / algebra / percentages: use exact arithmetic (fractions.Fraction) or search over integers;
   - paths / grids / graphs: BFS or Dijkstra; scheduling with dependencies: longest path (critical path);
   - counting / sets: inclusion-exclusion and, if feasible, verify by brute-force enumeration.
3. Write plain top-level code (no input(), no `if __name__` guard). It MUST call print() at the end:
   NUM_SOLUTIONS: <the TRUE number of distinct final answers that satisfy all constraints>
   ANSWER: <one final answer in exactly the required format>
   Never print 0 to mean "not unique": print the real count, and still print an answer.
   The answer must be COMPUTED by the program and printed from a variable: never type the answer as a
   literal (e.g. print("ANSWER: 7") is forbidden).
4. If the problem lists answer options, copy them verbatim into a Python list OPTIONS and print the
   element of OPTIONS that matches your result (do not build the string yourself).
Reply with ONE ```python code block and nothing else."""

POT_USER = """Problem:
{problem}

Output format requirement: {hint}"""

POT_OBSERVATION = """Observation (output of running your program):
{observation}

{instruction}
Reply with ONE corrected, complete ```python code block."""

COT_SYSTEM = """You are an expert at math, logic puzzles and careful multi-step reasoning. Problems may be in Persian (Farsi).
Solve the problem step by step. Identify every condition, solve, then VERIFY your answer against each condition one by one.
If more than one answer seems possible, re-read the problem: use every condition, and pick the answer the question intends.
End your reply with exactly one line:
FINAL ANSWER: <answer in exactly the required format>"""

COT_USER = """Problem:
{problem}

Output format requirement: {hint}"""

JUDGE_SYSTEM = """You are a strict verifier. Several independent solvers proposed different answers to the same problem.
Check EACH candidate against EVERY condition of the problem, explicitly, one condition at a time
(arithmetic: recompute; logic: test each statement). Exactly one answer is intended.
Choose the candidate that satisfies all conditions; if none does, solve the problem yourself.
End your reply with exactly one line:
FINAL ANSWER: <answer in exactly the required format>"""

JUDGE_USER = """Problem:
{problem}

Output format requirement: {hint}

Candidate answers (with how many solvers produced each):
{candidates}"""
