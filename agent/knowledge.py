"""Generic Persian-language helpers injected into prompts.

Small local models often mis-translate Persian calendar words (e.g. they map دوشنبه to
'Tuesday' because it contains 'دو' = two). When such words appear in a problem we append a
fixed glossary. This is general language knowledge, not information about any test problem.
"""
import re

from .formatter import to_ascii_digits

WEEKDAYS = ("Persian weekday names (the Iranian week starts on Saturday):\n"
            "شنبه = Saturday, یکشنبه = Sunday, دوشنبه = Monday, سه‌شنبه = Tuesday, "
            "چهارشنبه = Wednesday, پنج‌شنبه = Thursday, جمعه = Friday.\n"
            "A range 'X تا Y' includes every day from X to Y in this order (e.g. شنبه تا سه‌شنبه = Saturday..Tuesday).")

MONTHS = ("Persian (Solar Hijri) months in order: 1 فروردین, 2 اردیبهشت, 3 خرداد, 4 تیر, 5 مرداد, "
          "6 شهریور (months 1-6 have 31 days), 7 مهر, 8 آبان, 9 آذر, 10 دی, 11 بهمن (30 days), "
          "12 اسفند (29 days, 30 in leap years).")

TERMS = ("Useful Persian terms: زودتر/قبل از = earlier/before, دیرتر/بعد از = later/after, "
         "بلافاصله = immediately, دقیقاً = exactly, حداقل = at least / minimum, حداکثر = at most / maximum, "
         "متمایز = distinct, مجموع = sum, تفاضل = difference, حاصل‌ضرب = product, برابر = times/equal, "
         "راستگو = truth-teller, دروغگو = liar.")


_SEP = "[\\s\u200c]?"
_DAYS = [  # longest names first so that 'شنبه' does not match inside 'سه‌شنبه'
    ("پنج" + _SEP + "شنبه", "Thursday"), ("چهار" + _SEP + "شنبه", "Wednesday"),
    ("سه" + _SEP + "شنبه", "Tuesday"), ("دو" + _SEP + "شنبه", "Monday"),
    ("یک" + _SEP + "شنبه", "Sunday"), ("شنبه", "Saturday"), ("جمعه", "Friday"),
]
_LETTER = "\u0621-\u063A\u0641-\u064A\u0671-\u06D3"   # Persian/Arabic letters (not punctuation)
_DAY_RE = re.compile(f"(?<![{_LETTER}\u200c])(" + "|".join(p for p, _ in _DAYS) + f")(?![{_LETTER}])")


def _annotate_day(m):
    word = m.group(1)
    for pat, eng in _DAYS:
        if re.fullmatch(pat, word):
            return f"{word} ({eng})"
    return word


def annotate_days(text):
    """Inline translation: 'سه‌شنبه' -> 'سه‌شنبه (Tuesday)'. Small models misread these words."""
    return _DAY_RE.sub(_annotate_day, text)


def augment(problem):
    """Problem text with ASCII digits, inline weekday translations and glossary notes."""
    text = annotate_days(to_ascii_digits(problem).strip())
    flat = re.sub(r"[\s‌]", "", text)
    notes = []
    if re.search(r"شنبه|جمعه", flat):
        notes.append(WEEKDAYS)
    if re.search(r"فروردین|اردیبهشت|خرداد|شهریور|مهرماه|آبان|آذر|بهمن|اسفند", flat):
        notes.append(MONTHS)
    if re.search(r"[؀-ۿ]", text):
        notes.append(TERMS)
    if notes:
        text += "\n\n[Reference notes for reading the problem]\n" + "\n".join(notes)
    return text
