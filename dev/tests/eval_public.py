"""Score an output.json against a gold file:  python dev/tests/eval_public.py output.json dev/gold_hidden_like.json"""
import json, sys
pred = json.load(open(sys.argv[1], encoding="utf-8")); gold = json.load(open(sys.argv[2], encoding="utf-8"))
pred = {p["id"]: p["answer"] for p in (pred if isinstance(pred, list) else [pred])}
ok = 0
for pid, acc in gold.items():
    acc = acc if isinstance(acc, list) else [acc]
    good = pred.get(pid) in acc; ok += good
    print(("✔" if good else "✘"), pid, repr(pred.get(pid)), "expected", acc)
print(f"Accuracy = {ok}/{len(gold)} = {ok/len(gold):.0%}")
