"""Analyzer (output contract) + deterministic answer normalizer.

The auto-grader compares the `answer` field exactly, so every answer goes through
`finalize(raw, spec)` which forces it into the format the problem asked for.
Nothing here depends on specific public problems: it reads format hints from the text.
"""
import difflib
import re

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PERSIAN_CHARS = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_PLACEHOLDER = re.compile(r"<\s*([^<>\n]{1,40}?)\s*>")


def to_ascii_digits(s):
    return (s or "").translate(_FA_DIGITS).replace("\u066b", ".").replace("\u066c", ",")


def _simplify(s):
    return re.sub(r"[\s\u200c\u200f\u200e]+", " ", to_ascii_digits(s)).strip()


def _key(s):
    """Comparison key: lowercase, no spaces/punctuation."""
    return re.sub(r"[\W_]+", "", to_ascii_digits(s).lower())


# ----------------------------------------------------------------------- analyzer
def analyze(problem):
    """Infer the required answer format from the problem text (the 'output contract')."""
    text = to_ascii_digits(problem).replace("\r", "")
    flat = text.replace("\u200c", "").lower()
    lines = [l.strip() for l in text.split("\n")]
    spec = {"kind": "free", "options": [], "template": None, "keys": []}

    # 1) explicit template, e.g.  Nima=<integer>, Sara=<integer>, Reza=<integer>
    for l in lines:
        if len(_PLACEHOLDER.findall(l)) >= 1 and ("=" in l or "," in l or ":" in l):
            tpl = l.strip().strip("`\"' ")
            if tpl.startswith("<") and not tpl.startswith("<" + _PLACEHOLDER.findall(tpl)[0]):
                tpl = tpl[1:]                      # broken RTL copy like "<Nima=<integer>"
            if tpl.count("<") > tpl.count(">"):
                tpl += ">"
            spec.update(kind="template", template=tpl,
                        keys=re.findall(r"([^\s,;=:<>]+)\s*[=:]\s*<", tpl))
            break

    # 2) a block of >=2 short Latin-only lines after a "one of the following" phrase
    if spec["kind"] == "free" and re.search(r"یکی از|گزینه|one of|options?|choices?|choose", flat):
        runs, cur = [], []
        for l in lines + [""]:
            ok = (0 < len(l) <= 80 and not _PERSIAN_CHARS.search(l) and re.search(r"[A-Za-z0-9]", l)
                  and not re.match(r"^[-•*]", l) and "<" not in l)
            if ok:
                cur.append(l)
            else:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
        if runs:
            spec.update(kind="options", options=runs[-1])

    if spec["kind"] == "free":
        if re.search(r"\bletter\b|حرف(?![\u0600-\u06FF])", flat):
            spec["kind"] = "letter"
        elif re.search(r"\bcode\b|\bpin\b|password|کد(?![\u0600-\u06FF])|رمز", flat) and re.search(r"رقم|digit", flat):
            spec["kind"] = "digits"
        elif re.search(r"integer|whole number|\bnumber\b|عدد|اعداد|چند", flat):
            spec["kind"] = "integer"
    return spec


def format_hint(spec):
    k = spec["kind"]
    if k == "template":
        return f"The final answer MUST be exactly in this format: {spec['template']} (replace each <...> with the value)."
    if k == "options":
        return "The final answer MUST be exactly one of these options, copied verbatim:\n" + "\n".join(spec["options"])
    if k == "letter":
        return "The final answer MUST be a single letter only."
    if k == "digits":
        return "The final answer MUST be only the digits of the code (e.g. 123), nothing else."
    if k == "integer":
        return "The final answer MUST be a single integer only (digits, no units, no words)."
    return "The final answer must be as short as possible: only the value that is asked for, no explanation."


# --------------------------------------------------------------------- normalizer
def clean(raw):
    if raw is None:
        return ""
    s = to_ascii_digits(str(raw))
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S | re.I)
    m = re.findall(r"\\boxed\{([^{}]*)\}", s)
    if m:
        s = m[-1]
    m = re.findall(r"(?im)^\s*(?:\**\s*)?(?:final\s*answer|answer|پاسخ(?:\s*نهایی)?|جواب)\s*\**\s*[:：=]\s*(.+)$", s)
    if m:
        s = m[-1]
    s = s.replace("\\text", "")
    s = re.sub(r"[*`$]|\\\(|\\\)|\\\[|\\\]", "", s)
    lines = [l.strip() for l in s.strip().split("\n") if l.strip()]
    s = lines[-1] if lines else ""
    s = s.strip().strip("\"'«»“”").strip()
    s = re.sub(r"[.。!؛;]+$", "", s).strip()
    return s


def _numbers(s):
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    return re.findall(r"-?\d+(?:\.\d+)?", s)


def _as_int_str(n):
    try:
        f = float(n)
        if abs(f - round(f)) < 1e-6:
            return str(int(round(f)))
    except ValueError:
        pass
    return n


def finalize(raw, spec):
    """Return the answer string in the required format ('' if nothing usable)."""
    s = clean(raw)
    if not s:
        return ""
    k = spec["kind"]

    if k == "template":
        tpl, keys = spec["template"], spec["keys"]
        n_ph = len(_PLACEHOLDER.findall(tpl))
        vals = []
        if keys and len(keys) == n_ph:
            for key in keys:
                m = re.search(re.escape(key) + r"\s*[=:]\s*(-?\d+(?:\.\d+)?|[^\s,;]+)", s, re.I)
                if not m:
                    vals = []
                    break
                vals.append(m.group(1))
        if not vals:
            nums = _numbers(s)
            if len(nums) == n_ph:
                vals = nums
        if vals:
            it = iter(_as_int_str(v) if re.fullmatch(r"-?\d+(?:\.\d+)?", v) else v for v in vals)
            return _PLACEHOLDER.sub(lambda _m: next(it), tpl)
        return s

    if k == "options":
        opts = spec["options"]
        ks = _key(s)
        for o in opts:
            if _key(o) == ks:
                return o
        hits = [(ks.rfind(_key(o)), len(_key(o)), o) for o in opts if _key(o) and _key(o) in ks]
        if hits:
            return max(hits)[2]
        best = max(opts, key=lambda o: difflib.SequenceMatcher(None, _key(o), ks).ratio())
        if difflib.SequenceMatcher(None, _key(best), ks).ratio() >= 0.85:   # only near-exact typos
            return best
        return s

    if k == "letter":
        m = (re.findall(r"(?<![A-Za-z])([A-Z])(?![A-Za-z])", s)
             or re.findall(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])", s))
        return m[-1].upper() if m else s

    if k == "digits":
        m = re.findall(r"\d+", s.replace(" ", ""))
        return m[-1] if m else s

    if k == "integer":
        nums = _numbers(s)
        return _as_int_str(nums[-1]) if nums else s

    return s


def same(a, b):
    return _key(a) == _key(b) and _key(a) != ""


def is_valid(ans, spec):
    """Does the answer satisfy the format contract?"""
    if not ans:
        return False
    k = spec["kind"]
    if k == "options":
        return ans in spec["options"]
    if k == "template":
        parts = _PLACEHOLDER.split(spec["template"])[::2]
        pattern = r"(-?\w[\w.\-]*)".join(re.escape(p) for p in parts)
        return bool(re.fullmatch(pattern, ans))
    if k == "letter":
        return bool(re.fullmatch(r"[A-Z]", ans))
    if k == "digits":
        return ans.isdigit()
    if k == "integer":
        return bool(re.fullmatch(r"-?\d+", ans))
    return len(ans) <= 200
