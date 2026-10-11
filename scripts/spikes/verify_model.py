"""Evaluate every formula in the business model with pycel, then check key outputs against an independent Python model.

    python scripts/spikes/verify_model.py results/business_model.xlsx

Inputs are read from the workbook's typed cells, so the checks still hold after an input changes (for example
Assumptions!B5 once M2 measures the cost per audit). Prices are read from src/llm.py.
"""
import math
import sys
from pathlib import Path

from openpyxl import load_workbook
from pycel import ExcelCompiler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.llm import PRICES      # noqa: E402

path = sys.argv[1]
wb = load_workbook(path)
xl = ExcelCompiler(filename=path)
ev = lambda ref: xl.evaluate(ref)      # noqa: E731

errors, count = [], 0
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("="):
                count += 1
                v = ev("%s!%s" % (ws.title, c.coordinate))
                if v is None or (isinstance(v, str) and v.startswith("#")):
                    errors.append((ws.title, c.coordinate, v, c.value))
print("formulas evaluated:", count, "| errors:", len(errors))
for e in errors[:10]:
    print("  ", e)

checks = []


def check(name, got, want):
    ok = (got == want) if isinstance(want, str) else (not isinstance(got, str) and math.isclose(float(got), want, rel_tol=1e-9, abs_tol=1e-9))
    checks.append(ok)
    fmt = lambda x: x if isinstance(x, str) else round(x, 5)   # noqa: E731
    print("%-62s sheet=%-22s python=%-22s %s" % (name[:62], fmt(got), fmt(want), "OK" if ok else "MISMATCH"))


# ---- cost per audit: recompute the Cost_Estimate table from its typed sizes and src/llm.py prices
E = wb["Cost_Estimate"]
inp = {r: E.cell(row=r, column=2).value for r in range(5, 14)}
assert (inp[5], inp[6]) == PRICES["deepseek-v4-pro"] and (inp[7], inp[8]) == PRICES["deepseek-flash"], "prices drifted from src/llm.py"
total = 0.0
for r in range(17, 22):
    model, n, s, u = (E.cell(row=r, column=c).value for c in (3, 4, 5, 6))
    n = inp[12] if isinstance(n, str) else n
    comp = inp[11] if model == "deepseek-flash" else inp[10]
    p_in, p_out = PRICES[model]
    total += n * ((s + u) / inp[9] * p_in + comp * p_out) / 1e6
estimate = total * (1 + inp[13])
check("Cost_Estimate!B26 estimated LLM cost per audit", ev("Cost_Estimate!B26"), estimate)
llm = wb["Assumptions"]["B5"].value
print("Assumptions!B5 (the single cost variable) = %.4f; |B5 - estimate| = %.5f%s" % (
    llm, abs(llm - estimate), " (still the estimate)" if abs(llm - estimate) < 0.0005 else " (replaced, e.g. by the measured figure)"))

# ---- monthly model and unit economics, from the typed Assumptions
A = wb["Assumptions"]
LABELS = {"Pay-per-audit price (HYPOTHESIS)": "price_audit", "Audits bought per card charge (credit pack)": "pack",
          "Hobbyist plan price (HYPOTHESIS)": "plan_price", "Audits included in the hobbyist plan": "plan_audits",
          "Audits a subscriber runs per month": "plan_used", "Audits a pay-per-audit user runs per month": "ppa_audits",
          "Share of users on the hobbyist plan": "mix", "Data cost per audit": "data",
          "Payment fee, share of the charge": "fee_pct", "Payment fee, fixed per charge": "fee_fixed",
          "Paying users at start": "start", "New paying users in month 1": "new1", "Monthly growth in new users": "g",
          "Monthly churn": "churn", "Acquisition cost per new user (CAC)": "cac", "Hosting per month": "hosting",
          "neatlogs per month": "neat", "Team cost per month": "team", "Starting cash": "cash"}
rows = {LABELS[A.cell(row=r, column=1).value]: r for r in range(8, A.max_row + 1) if A.cell(row=r, column=1).value in LABELS}
assert len(rows) == len(LABELS), "missing assumptions: %s" % (set(LABELS.values()) - set(rows))


def model(p, months=12):
    users, cash, out = p["start"], p["cash"], {k: [] for k in ("users", "audits", "rev", "gm", "llm", "op", "cash")}
    for m in range(1, months + 1):
        new = p["new1"] * (1 + p["g"]) ** (m - 1)
        end = users + new - users * p["churn"]
        subs, ppa = end * p["mix"], end * (1 - p["mix"])
        a_ppa = ppa * p["ppa_audits"]
        audits = subs * p["plan_used"] + a_ppa
        rev = subs * p["plan_price"] + a_ppa * p["price_audit"]
        fees = subs * (p["plan_price"] * p["fee_pct"] + p["fee_fixed"]) + a_ppa * (p["price_audit"] * p["fee_pct"] + p["fee_fixed"] / p["pack"])
        gross = rev - fees - audits * (llm + p["data"])
        op = gross - new * p["cac"] - p["hosting"] - p["neat"] - p["team"]
        cash += op
        for k, v in (("users", end), ("audits", audits), ("rev", rev), ("gm", gross / rev if rev else 0),
                     ("llm", audits * llm), ("op", op), ("cash", cash)):
            out[k].append(v)
        users = end
    return out


for col, name in (("B", "Base"), ("C", "Growth")):
    p = {k: A["%s%d" % (col, r)].value for k, r in rows.items()}
    o = model(p)
    first_neg = next((i + 1 for i, v in enumerate(o["cash"]) if v < 0), "none within 12 months")
    first_profit = next((i + 1 for i, v in enumerate(o["op"]) if v >= 0), "not within 12 months")
    runway = "not burning cash" if o["op"][11] >= 0 else max(0, o["cash"][11] / -o["op"][11])
    expect = {11: o["users"][5], 12: o["users"][11], 13: o["audits"][11], 14: o["rev"][11], 15: o["gm"][11],
              16: sum(o["rev"]), 17: sum(o["llm"]), 18: sum(o["op"]), 19: min(o["cash"]), 20: o["cash"][11],
              21: first_neg, 22: runway, 23: first_profit, 24: max(0, -min(o["cash"]))}
    for row, want in expect.items():
        check("%s Summary!%s%d %s" % (name, col, row, wb["Summary"].cell(row=row, column=1).value), ev("Summary!%s%d" % (col, row)), want)
    fee_audit = p["price_audit"] * p["fee_pct"] + p["fee_fixed"] / p["pack"]
    c_audit = p["price_audit"] - fee_audit - llm - p["data"]
    c_sub = p["plan_price"] - (p["plan_price"] * p["fee_pct"] + p["fee_fixed"]) - p["plan_used"] * (llm + p["data"])
    blended = p["mix"] * c_sub + (1 - p["mix"]) * p["ppa_audits"] * c_audit
    for row, want in ((9, c_audit), (10, c_audit / p["price_audit"]), (17, c_sub), (18, c_sub / p["plan_price"]),
                      (23, blended), (27, blended / p["churn"] / p["cac"])):
        check("%s Unit_Economics!%s%d %s" % (name, col, row, wb["Unit_Economics"].cell(row=row, column=1).value),
              ev("Unit_Economics!%s%d" % (col, row)), want)

print("ALL CHECKS PASS" if all(checks) and not errors else "CHECKS FAILED")
sys.exit(0 if all(checks) and not errors else 1)
