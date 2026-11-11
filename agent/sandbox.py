"""Run model-written Python in a separate, isolated, time-limited process (the agent's 'tool')."""
import os
import re
import subprocess
import sys
import tempfile

FORBIDDEN = re.compile(
    r"\b(subprocess|socket|shutil|urllib|requests|http\.client|ctypes|multiprocessing)\b"
    r"|os\.(system|popen|remove|unlink|rmdir|removedirs|kill|exec\w*|spawn\w*)"
    r"|__import__\s*\(|\binput\s*\("
)


# Small models often assign ANSWER / NUM_SOLUTIONS but forget to print them.
AUTO_PRINT = """

# --- appended by the agent: report result variables if they exist ---
for _n in ("NUM_SOLUTIONS", "ANSWER"):
    if _n in globals():
        print("AUTO_" + _n + ":", globals()[_n])
"""


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S | re.I)
    if blocks:
        with_print = [b for b in blocks if "print" in b]
        return (with_print or blocks)[-1]
    if re.search(r"^\s*(import|from|def|for|print)\b", text, re.M):
        return text
    return ""


def run_python(code, timeout=20, max_out=6000):
    """Returns (ok, stdout, stderr)."""
    if not code.strip():
        return False, "", "No Python code block was found in your reply."
    bad = FORBIDDEN.search(code)
    if bad:
        return False, "", f"Forbidden construct '{bad.group(0)}'. Use only pure computation (itertools, math, fractions, collections)."
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "solution.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code + AUTO_PRINT)
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0",
               "PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
        try:
            p = subprocess.run([sys.executable, "-I", path], cwd=d, capture_output=True,
                               timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return False, "", f"Timeout: the program ran longer than {timeout}s. Use a smarter / smaller search."
    out = p.stdout.decode("utf-8", "replace")[-max_out:]
    err = p.stderr.decode("utf-8", "replace")[-max_out:]
    return p.returncode == 0, out, err


def parse_program_output(out):
    """Find 'ANSWER: ...' (last one) and optional 'NUM_SOLUTIONS: k'.
    Lines the program printed itself win over the AUTO_ fallback lines added by the agent."""
    found = {"answer": None, "nsol": None, "auto_answer": None, "auto_nsol": None}
    plain = []
    for line in out.splitlines():
        s = line.strip()
        auto = s.startswith("AUTO_")
        body = s[5:] if auto else s
        m = re.match(r"(?i)answer\s*[:=]\s*(.*)$", body)
        if m and m.group(1).strip():
            found["auto_answer" if auto else "answer"] = m.group(1).strip()
            continue
        m = re.match(r"(?i)num_solutions\s*[:=]\s*\[?(\d+)", body)
        if m:
            found["auto_nsol" if auto else "nsol"] = int(m.group(1))
            continue
        if s and not auto:
            plain.append(s)
    answer = found["answer"] or found["auto_answer"] or (plain[-1] if plain else None)
    nsol = found["nsol"] if found["nsol"] is not None else found["auto_nsol"]
    return answer, nsol


def hardcoded_answer(code):
    """True if the program prints a literal ANSWER, or only ever assigns ANSWER a literal value."""
    literal_assign = computed_assign = False
    for line in code.splitlines():
        t = line.split("#", 1)[0].strip()
        if not t or "ANSWER" not in t:
            continue
        m = re.search(r"(?:^|[:;]\s*)ANSWER\s*=(?!=)\s*(.+)$", t)
        if m:
            v = m.group(1).strip()
            if v in ('""', "''", "None"):
                continue                     # harmless default before the real computation
            if re.fullmatch(r"(['\"])[^'\"{}]*\1|-?\d+(\.\d+)?", v):
                literal_assign = True
            else:
                computed_assign = True
            continue
        m = re.match(r"print\s*\((.*)\)\s*$", t)
        if m and not re.search(r"\bf['\"]", m.group(1)):
            rest = re.sub(r"'[^']*'|\"[^\"]*\"", "", m.group(1))
            if not re.search(r"[A-Za-z_]", rest):
                return True
    return literal_assign and not computed_assign
