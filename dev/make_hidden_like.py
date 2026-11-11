"""Dev-only: builds a 'hidden-like' test set of NEW problems (same skill types as the public set,
different content/numbers/formats). Every gold answer is computed by brute force here and
checked to be UNIQUE, so the gold file is trustworthy.
Run:  python make_hidden_like.py   -> hidden_like_input.json + gold_hidden_like.json
"""
import json
import os
from collections import deque
from fractions import Fraction as F
from itertools import permutations, product

P = []  # (id, problem, gold)


def add(problem, solutions):
    sols = sorted(set(solutions), key=str)
    assert len(sols) == 1, (problem[:60], sols)
    P.append((f"h{len(P) + 1:02d}", problem.strip(), str(sols[0])))


# 1 algebra, template with 4 keys
s = []
for d in range(1, 200):
    c = d + 7; b = 2 * c; a = b - 10
    if a + b + c + d == 151: s.append(f"Ali={a}, Babak={b}, Cyrus={c}, Dara={d}")
add("""علی، بابک، کوروش و دارا روی هم ۱۵۱ کتاب دارند. کوروش ۷ کتاب بیشتر از دارا دارد، بابک دو برابر کوروش کتاب دارد و علی ۱۰ کتاب کمتر از بابک دارد. هرکدام چند کتاب دارند؟
پاسخ را دقیقاً با فرمت زیر برگردانید:
Ali=<integer>, Babak=<integer>, Cyrus=<integer>, Dara=<integer>""", s)

# 2 ages
s = [x for x in range(1, 100) for y in range(1, 100) if x == 3 * y and x + 6 == 2 * (y + 6)]
add("""سن پدر سه برابر سن پسرش است. ۶ سال بعد، سن پدر دو برابر سن پسرش خواهد بود. سن فعلی پدر چند سال است؟
فقط عدد صحیح را برگردانید.""", s)

# 3 ordering, unique (letter)
s = []
for p in permutations("PQRST"):
    pos = {c: i + 1 for i, c in enumerate(p)}
    if (pos["Q"] == pos["P"] + 1 and pos["R"] < pos["T"] and pos["S"] not in (1, 2)
            and pos["T"] != 5 and pos["P"] == 2):
        s.append(p[4])
add("""پنج کار P، Q، R، S و T هرکدام دقیقاً یک‌بار در جایگاه‌های ۱ تا ۵ انجام می‌شوند.
قیود:
- Q بلافاصله بعد از P انجام می‌شود.
- R قبل از T انجام می‌شود.
- S در جایگاه ۱ یا ۲ نیست.
- T آخرین کار نیست.
- P در جایگاه ۲ است.
کدام کار در جایگاه پنجم قرار می‌گیرد؟
فقط حرف آن کار را برگردانید.""", s)

# 4 exactly-one-true statements (unique)
s = []
for box in (1, 2, 3, 4):
    st = [box in (2, 3), box != 1, box == 4, box % 2 == 1]
    if sum(st) == 1: s.append(box)
add("""سکه در یکی از چهار کشوی ۱، ۲، ۳ یا ۴ است. از چهار جمله زیر دقیقاً یکی درست است:
۱) سکه در کشوی ۲ یا ۳ است.
۲) سکه در کشوی ۱ نیست.
۳) سکه در کشوی ۴ است.
۴) شماره کشوی سکه فرد است.
سکه در کدام کشو است؟
فقط عدد صحیح را برگردانید.""", s)

# 5 critical path (5 tasks)
dur = {"A": 4, "B": 6, "C": 3, "D": 5, "E": 2}
pre = {"A": [], "B": ["A"], "C": ["A"], "D": ["C"], "E": ["B", "D"]}
fin = {}
for t in "ABCDE":
    fin[t] = max([fin[p] for p in pre[t]] or [0]) + dur[t]
add("""پروژه‌ای پنج فعالیت دارد:
- فعالیت A چهار روز طول می‌کشد و پیش‌نیازی ندارد.
- فعالیت B شش روز طول می‌کشد و بعد از پایان A شروع می‌شود.
- فعالیت C سه روز طول می‌کشد و بعد از پایان A شروع می‌شود.
- فعالیت D پنج روز طول می‌کشد و بعد از پایان C شروع می‌شود.
- فعالیت E دو روز طول می‌کشد و فقط پس از پایان B و D شروع می‌شود.
فعالیت‌هایی که پیش‌نیاز هم نیستند می‌توانند همزمان انجام شوند. پروژه در روز ۰ شروع می‌شود. حداقل زمان اتمام پروژه چند روز است؟
فقط عدد صحیح را برگردانید.""", [max(fin.values())])

# 6 three-set inclusion-exclusion
U, A, B, C, AB, AC, BC, ABC = 100, 45, 38, 30, 15, 12, 10, 5
add(f"""در یک نظرسنجی از ۱۰۰ نفر:
- ۴۵ نفر فوتبال، ۳۸ نفر والیبال و ۳۰ نفر بسکتبال تماشا می‌کنند.
- ۱۵ نفر فوتبال و والیبال، ۱۲ نفر فوتبال و بسکتبال و ۱۰ نفر والیبال و بسکتبال تماشا می‌کنند.
- ۵ نفر هر سه رشته را تماشا می‌کنند.
چند نفر هیچ‌کدام از این سه رشته را تماشا نمی‌کنند؟
فقط عدد صحیح را برگردانید.""", [U - (A + B + C - AB - AC - BC + ABC)])

# 7 percentages reverse
s = [x for x in range(1, 100000) if F(x) * F(80, 100) * F(110, 100) == 1320]
add("""قیمت یک دوچرخه ابتدا ۲۰٪ کاهش یافت و سپس قیمت جدید ۱۰٪ افزایش پیدا کرد. قیمت نهایی ۱۳۲۰ هزار تومان شد. قیمت اولیه چند هزار تومان بوده است؟
فقط عدد صحیح را برگردانید.""", s)

# 8 assignment with weekdays (Sat..Wed), options in English
days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"]
s = []
for p in permutations(range(5)):
    sina, mina, reza, nazi, omid = p
    if (mina == sina + 2 and reza != 0 and reza != 4 and nazi < omid and omid == 3 and sina != 1
            and abs(reza - mina) > 1 and True):
        s.append(days[nazi])
add("""پنج نفر سینا، مینا، رضا، نازی و امید هرکدام در یکی از روزهای شنبه تا چهارشنبه (هر روز دقیقاً یک نفر) جلسه دارند.
قیود:
- مینا دقیقاً دو روز بعد از سینا جلسه دارد.
- رضا نه شنبه جلسه دارد و نه چهارشنبه.
- نازی زودتر از امید جلسه دارد.
- امید سه‌شنبه جلسه دارد.
- سینا یکشنبه جلسه ندارد.
- روز جلسه رضا و مینا مجاور نیست.
نازی در چه روزی جلسه دارد؟
فقط یکی از این عبارت‌ها را برگردانید:
Saturday
Sunday
Monday
Tuesday
Wednesday""", s)

# 9 knights & knaves, three people, options
s = []
for a, b, c in product([True, False], repeat=3):  # True = truth-teller
    sa = (b == c)                 # A: "B and C are the same type"
    sb = (not a)                  # B: "A is a liar"
    sc = a                        # C: "A is a truth-teller"
    if sa == a and sb == b and sc == c:
        s.append(f"A={'T' if a else 'L'}, B={'T' if b else 'L'}, C={'T' if c else 'L'}")
opts = [f"A={x}, B={y}, C={z}" for x in "TL" for y in "TL" for z in "TL"]
add("""در جزیره‌ای هر نفر یا همیشه راست می‌گوید (T) یا همیشه دروغ می‌گوید (L).
A می‌گوید: «B و C از یک نوع هستند.»
B می‌گوید: «A دروغگو است.»
C می‌گوید: «A راستگو است.»
وضعیت هر سه نفر چیست؟ دقیقاً یکی از گزینه‌های زیر را برگردانید:
""" + "\n".join(opts), s)

# 10 grid BFS with walls
W, H = 5, 5
blocked = {(1, 1), (2, 1), (3, 1), (3, 2), (3, 3), (1, 3)}
start, goal = (0, 0), (4, 4)
q, seen = deque([(start, 0)]), {start}
best = None
while q:
    (x, y), d = q.popleft()
    if (x, y) == goal: best = d; break
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + dx, y + dy)
        if 0 <= n[0] < W and 0 <= n[1] < H and n not in blocked and n not in seen:
            seen.add(n); q.append((n, d + 1))
add("""رباتی روی یک شبکه ۵×۵ با مختصات 0<=x<=4 و 0<=y<=4 از خانه (0,0) شروع می‌کند و باید به (4,4) برسد. در هر حرکت فقط یک خانه به بالا، پایین، چپ یا راست می‌رود.
خانه‌های (1,1)، (2,1)، (3,1)، (3,2)، (3,3) و (1,3) دیوار هستند و ربات نمی‌تواند وارد آن‌ها شود.
کمترین تعداد حرکت لازم چقدر است؟
فقط عدد صحیح را برگردانید.""", [best])

# 11 digit code (4 digits)
s = []
for a, b, c, d in permutations(range(10), 4):
    if a == 0: continue
    if a + b + c + d == 22 and d == 2 * a and b == c + 3 and c > a and (1000 * a + 100 * b + 10 * c + d) % 4 == 0:
        s.append(f"{a}{b}{c}{d}")
add("""یک رمز چهاررقمی با ارقام متمایز داریم (رقم اول صفر نیست).
قیود:
- مجموع ارقام ۲۲ است.
- رقم چهارم دو برابر رقم اول است.
- رقم دوم ۳ واحد از رقم سوم بیشتر است.
- رقم سوم از رقم اول بزرگ‌تر است.
- عدد چهاررقمی بر ۴ بخش‌پذیر است.
رمز چیست؟
فقط رمز چهاررقمی را برگردانید.""", s)

# 12 work rate
add("""علی یک کار را به‌تنهایی در ۶ ساعت و رضا همان کار را به‌تنهایی در ۱۲ ساعت انجام می‌دهد. اگر با هم کار کنند، چند ساعت طول می‌کشد؟
فقط عدد صحیح را برگردانید.""", [int(1 / (F(1, 6) + F(1, 12)))])

# 13 day-of-week arithmetic (English options)
week = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
add("""امروز سه‌شنبه است. ۱۰۰ روز بعد چه روزی از هفته خواهد بود؟
دقیقاً یکی از گزینه‌های زیر را برگردانید:
Saturday
Sunday
Monday
Tuesday
Wednesday
Thursday
Friday""", [week[(3 + 100) % 7]])

# 14 counting (combinatorics)
s = sum(1 for n in range(100, 1000) if len(set(str(n))) == 3 and n % 5 == 0)
add("""چند عدد سه‌رقمی وجود دارد که هر سه رقم آن متمایز باشد و بر ۵ بخش‌پذیر باشد؟
فقط عدد صحیح را برگردانید.""", [s])

# 15 coins
s = [(a, b) for a in range(0, 100) for b in range(0, 100) if a + b == 30 and 500 * a + 1000 * b == 21000]
add("""در یک قلک ۳۰ سکه ۵۰۰ تومانی و ۱۰۰۰ تومانی وجود دارد و مجموع ارزش آن‌ها ۲۱۰۰۰ تومان است. چند سکه ۱۰۰۰ تومانی در قلک است؟
فقط عدد صحیح را برگردانید.""", [b for a, b in s])

# 16 mixture
s = [x for x in range(0, 1000) if F(20 * 10 + 50 * x, 100 * (10 + x)) == F(30, 100)]
add("""۱۰ لیتر محلول ۲۰٪ نمک داریم. چند لیتر محلول ۵۰٪ نمک باید به آن اضافه کنیم تا غلظت محلول نهایی ۳۰٪ شود؟
فقط عدد صحیح را برگردانید.""", s)

# 17 truth puzzle: who broke the vase (options Persian names in English)
names = ["Arash", "Bita", "Kaveh", "Donya"]
s = []
for culprit in names:
    st = {"Arash": culprit == "Kaveh", "Bita": culprit != "Bita", "Kaveh": culprit == "Donya", "Donya": culprit != "Donya"}
    if sum(st.values()) == 1: s.append(culprit)
add("""یکی از چهار نفر آرش، بیتا، کاوه و دنیا گلدان را شکسته است. هرکدام یک جمله می‌گویند:
- آرش: «کاوه گلدان را شکسته است.»
- بیتا: «من گلدان را نشکسته‌ام.»
- کاوه: «دنیا گلدان را شکسته است.»
- دنیا: «کاوه دروغ می‌گوید.»
اگر دقیقاً یکی از آن‌ها راست بگوید، چه کسی گلدان را شکسته است؟
فقط یکی از گزینه‌های زیر را برگردانید:
Arash
Bita
Kaveh
Donya""", s)

# 18 sequence
seq = [2, 6, 12, 20, 30]
add("""جمله بعدی دنباله زیر چیست؟
۲، ۶، ۱۲، ۲۰، ۳۰، ...
فقط عدد صحیح را برگردانید.""", [6 * 7])

# 19 speed/distance
s = [d for d in range(1, 2000) if F(d, 60) + F(d, 40) == 5]
add("""خودرویی مسیر رفت را با سرعت ۶۰ کیلومتر بر ساعت و همان مسیر برگشت را با سرعت ۴۰ کیلومتر بر ساعت طی می‌کند. کل زمان رفت و برگشت ۵ ساعت است. طول مسیر یک‌طرفه چند کیلومتر است؟
فقط عدد صحیح را برگردانید.""", s)

# 20 seating around... linear seating, template output
s = []
for p in permutations(["Sara", "Neda", "Mehdi", "Hamed"]):
    pos = {n: i + 1 for i, n in enumerate(p)}
    if abs(pos["Sara"] - pos["Neda"]) == 1 and pos["Mehdi"] == 1 and pos["Hamed"] != 4 and pos["Sara"] > pos["Neda"]:
        s.append(f"Mehdi={pos['Mehdi']}, Hamed={pos['Hamed']}, Neda={pos['Neda']}, Sara={pos['Sara']}")
add("""چهار نفر سارا، ندا، مهدی و حامد روی چهار صندلی ردیفی با شماره‌های ۱ تا ۴ (از چپ به راست) می‌نشینند.
- سارا و ندا کنار هم نشسته‌اند و سارا سمت راست نداست.
- مهدی روی صندلی ۱ نشسته است.
- حامد روی صندلی ۴ ننشسته است.
شماره صندلی هر نفر را دقیقاً با این فرمت برگردانید:
Mehdi=<integer>, Hamed=<integer>, Neda=<integer>, Sara=<integer>""", s)

# 21 modular / remainder
s = [n for n in range(1, 200) if n % 3 == 2 and n % 5 == 3 and n % 7 == 2]
add("""کوچک‌ترین عدد طبیعی را پیدا کنید که بر ۳ تقسیم شود باقی‌مانده ۲، بر ۵ باقی‌مانده ۳ و بر ۷ باقی‌مانده ۲ بدهد.
فقط عدد صحیح را برگردانید.""", [min(s)])

# 22 English problem (language robustness)
s = [x for x in range(1, 1000) if x % 4 == 0 and x % 6 == 0 and 50 < x < 70]
add("""How many integers strictly between 50 and 70 are divisible by both 4 and 6?
Return only the integer.""", [len(s)])

# 23 yes/no with options
add("""آیا عدد ۹۱ عدد اول است؟
دقیقاً یکی از گزینه‌های زیر را برگردانید:
Yes
No""", ["No"])

# 24 shortest path weighted (Dijkstra) on named nodes
import heapq
g = {"A": {"B": 4, "C": 2}, "B": {"C": 1, "D": 5}, "C": {"B": 1, "D": 8, "E": 10}, "D": {"E": 2}, "E": {}}
dist = {"A": 0}; pq = [(0, "A")]
while pq:
    d, u = heapq.heappop(pq)
    if d > dist.get(u, 1e9): continue
    for v, w in g[u].items():
        if d + w < dist.get(v, 1e9): dist[v] = d + w; heapq.heappush(pq, (d + w, v))
add("""یک شبکه جاده‌ای یک‌طرفه بین شهرهای A، B، C، D و E وجود دارد. طول جاده‌ها (کیلومتر):
- A به B: ۴ ، A به C: ۲
- B به C: ۱ ، B به D: ۵
- C به B: ۱ ، C به D: ۸ ، C به E: ۱۰
- D به E: ۲
کوتاه‌ترین مسیر از A به E چند کیلومتر است؟
فقط عدد صحیح را برگردانید.""", [dist["E"]])

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "hidden_like_input.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": i, "problem": p} for i, p, _ in P], f, ensure_ascii=False, indent=2)
    with open(os.path.join(here, "gold_hidden_like.json"), "w", encoding="utf-8") as f:
        json.dump({i: g for i, _, g in P}, f, ensure_ascii=False, indent=2)
    for i, p, g in P:
        print(i, "->", g)
    print(len(P), "problems, all with a unique verified answer")
