"""Build results/business_model.xlsx: the Strategy Auditor business model, priced per audit, for import into cfo.ai.

    python scripts/spikes/build_business_model.py results/business_model.xlsx

One audit = one trading idea in, one evidence-backed verdict out. The single cost variable is
Assumptions!B5, "LLM cost per audit (USD)": an ESTIMATE until M2 measures it (AUDITOR_SPEC section 13).
The Cost_Estimate sheet shows how the estimate is built from the code: calls per audit (spec section 4),
prompt sizes from src/auditor/agents.py, and prices from src/llm.py, all read here at build time.
Every other number is an input on the Assumptions sheet; every other cell is a formula.
"""
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.auditor import agents                                   # noqa: E402
from src.auditor.plan import SCHEMA as PLAN_SCHEMA                 # noqa: E402
from src.llm import DEEPSEEK_THINKING, MODELS, PRICES            # noqa: E402

OUT = sys.argv[1]
MONTHS = 12
FIRST_COL = 3                      # month 1 in column C
LAST = get_column_letter(FIRST_COL + MONTHS - 1)
M6 = get_column_letter(FIRST_COL + 5)

FONT = "Arial"
BLUE, BLACK, GREEN, RED = "0000FF", "000000", "008000", "C00000"
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
THIN = Border(bottom=Side(style="thin", color="999999"))
BOX = Border(*(Side(style="medium", color=RED),) * 4)
USD = '$#,##0;($#,##0);"-"'
USD_CENTS = '$#,##0.00;($#,##0.00);"-"'
USD_MILLS = '$0.0000;($0.0000);"-"'
PCT = '0.0%;(0.0%);"-"'
COUNT = '#,##0.0;(#,##0.0);"-"'
INT = '#,##0;(#,##0);"-"'


def font(color=BLACK, bold=False, size=10, italic=False):
    return Font(name=FONT, color=color, bold=bold, size=size, italic=italic)


def header(ws, row, names):
    for i, h in enumerate(names, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = font(bold=True)
        c.fill = HEADER_FILL
        c.border = THIN


def note(cell, text, size=9):
    cell.value = text
    cell.font = font(size=size)
    cell.alignment = Alignment(wrap_text=True, vertical="top")


# ------------------------------------------------- cost per audit, from the code
SUFFIX = "\n\nReply with one JSON object that matches this JSON schema, and nothing else:\n"   # src/llm.py _deepseek_call


def system_chars(system, schema):
    return len(system + SUFFIX + json.dumps(schema))


DS = MODELS["deepseek"]
THINKING_OUT, REPORTER_OUT, P_INVALID, UPLIFT, CHARS_PER_TOKEN = 3000, 300, 0.10, 0.10, 4
if hasattr(agents, "NAYSAYER_FOLLOWUPS_SYSTEM"):     # M2 code present: read the real follow-up prompt
    NAYSAYER1_SYS = system_chars(agents.NAYSAYER_FOLLOWUPS_SYSTEM, agents.NAYSAYER_FOLLOWUPS_SCHEMA)
    NAYSAYER1_SRC = "System: NAYSAYER_FOLLOWUPS_SYSTEM (with the F1-F4 menu) + schema, read at build time."
else:                                               # ponytail: M1 code, assume the menu adds 1,500 chars
    NAYSAYER1_SYS = system_chars(agents.NAYSAYER_SYSTEM, agents.NAYSAYER_SCHEMA) + 1500
    NAYSAYER1_SRC = "M2 not built: NAYSAYER_SYSTEM + schema + 1,500 chars assumed for the F1-F4 menu."
# User prompt sizes, measured 2026-10-11: the audit loop (with M2 follow-ups) run with the fake LLM on the synthetic
# market of tests/test_auditor_run.py extended to all 50 tickers, for the three demo ideas; largest kept, rounded up.
CALLS = [   # label, agent, expected calls per audit (number or Cost_Estimate cell), system+schema chars, user chars, completion, source
    ("Planner: idea to plan v0", "planner", 1, system_chars(agents.PLANNER_SYSTEM, PLAN_SCHEMA), 60, THINKING_OUT,
     "System: PLANNER_SYSTEM + plan schema, read at build time. User: the idea as JSON, 34-56 chars measured."),
    ("Planner: one fix after an invalid plan", "planner", "=$B$12", system_chars(agents.PLANNER_SYSTEM, PLAN_SCHEMA), 300,
     THINKING_OUT, "Only when plan v0 fails validation (spec section 4). User: idea + validator message + instruction."),
    ("Naysayer call 1: doubts, choose follow-ups", "naysayer", 1, NAYSAYER1_SYS, 3300, THINKING_OUT,
     NAYSAYER1_SRC + " User: summary statistics, 2,502-3,262 chars measured."),
    ("Naysayer call 2: final critique", "naysayer", 1, system_chars(agents.NAYSAYER_SYSTEM, agents.NAYSAYER_SCHEMA),
     4500, THINKING_OUT, "System: NAYSAYER_SYSTEM + schema. User: summary statistics + follow-up results, "
     "3,249-4,019 chars measured."),
    ("Reporter: prose on the code-written report", "reporter", 1,
     system_chars(agents.REPORTER_SYSTEM, agents.REPORTER_SCHEMA), 10000, REPORTER_OUT,
     "The reserved 8th call, thinking off. User: the report draft, 6,164-7,831 chars measured on 3 synthetic years; "
     "real data has 13 year columns in the coverage table."),
]
for _, agent, *_ in CALLS:
    assert DS[agent] in ("deepseek-v4-pro", "deepseek-flash") and DEEPSEEK_THINKING[agent] == (DS[agent] == "deepseek-v4-pro")


def call_cost(agent, sys_chars, user_chars, completion):
    price_in, price_out = PRICES[DS[agent]]
    return ((sys_chars + user_chars) / CHARS_PER_TOKEN * price_in + completion * price_out) / 1e6


ESTIMATE = (1 + UPLIFT) * sum((P_INVALID if isinstance(n, str) else n) * call_cost(agent, s, u, c)
                              for _, agent, n, s, u, c, _ in CALLS)
LLM_INPUT = round(ESTIMATE, 3)     # the typed value of the single cost variable

wb = Workbook()

# ------------------------------------------------------------------ Assumptions
A = wb.active
A.title = "Assumptions"
A["A1"] = "Strategy Auditor: business model assumptions"
A["A1"].font = font(bold=True, size=13)
A["A2"] = ("Legend: blue = input you can change. Yellow = estimate or hypothesis to confirm (not measured). "
           "Black = formula. Green = link to another sheet. Column B feeds Model_Base, column C feeds Model_Growth.")
A["A2"].font = font(italic=True, size=9)
note(A["A3"], "Product: the Strategy Auditor, a paper-trading research tool. One audit = one trading idea in plain English, "
     "one evidence-backed verdict out (kill / inconclusive / promising / cannot audit), tested on 50 US large caps with "
     "historical data. Not financial advice. Sold two ways (pricing hypotheses): pay per audit, or a hobbyist plan with "
     "a monthly allowance of audits.")
A.merge_cells("A3:E3")
A.row_dimensions[3].height = 40

# The single cost variable: one cell, used by both scenarios.
A["A5"] = "LLM cost per audit (USD): ESTIMATE"
A["A5"].font = font(RED, bold=True)
c = A["B5"]
c.value = LLM_INPUT
c.number_format = '$0.000'
c.font = font(BLUE, bold=True)
c.fill = YELLOW
c.border = BOX
A["C5"] = "ESTIMATE"
A["C5"].font = font(RED, bold=True)
A["D5"] = "$ / audit"
A["D5"].font = font(size=9)
note(A["E5"], "THE single cost variable; both scenarios and every sheet use it. Estimate, not measured: built bottom-up "
     "on the Cost_Estimate sheet (%.4f, rounded) from calls per audit, prompt sizes in src/auditor/agents.py and "
     "DeepSeek prices in src/llm.py (peak, cache-miss: an upper bound). After M2, type the measured mean cost per "
     "audit here: section '9. Cost and trace' of each demo report (cost.usd in state.json), or the neatlogs traces." % ESTIMATE)
A.row_dimensions[5].height = 64

header(A, 7, ["Assumption", "Base", "Growth", "Unit", "Source or note"])
# key, label, base, growth, unit, number format, estimate or hypothesis (yellow)?, source
ROWS = [
    ("price_audit", "Pay-per-audit price (HYPOTHESIS)", 2, 2, "$ / audit", USD_CENTS, True,
     "Pricing hypothesis, not tested with customers."),
    ("pack", "Audits bought per card charge (credit pack)", 5, 5, "audits / charge", INT, True,
     "Hypothesis: audits sold in packs of 5 ($10). Charging every $2 audit separately would let Stripe's $0.30 "
     "fixed fee take 15% of revenue; a pack of 5 cuts it to 3%."),
    ("plan_price", "Hobbyist plan price (HYPOTHESIS)", 15, 15, "$ / month", USD_CENTS, True,
     "Pricing hypothesis, not tested with customers."),
    ("plan_audits", "Audits included in the hobbyist plan", 20, 20, "audits / month", INT, True,
     "Hypothesis. No overage is sold in this model."),
    ("plan_used", "Audits a subscriber runs per month", 10, 10, "audits / month", INT, True,
     "Owner estimate. The plan beats pay-per-audit above 7.5 audits a month, so subscribers are the heavier users."),
    ("ppa_audits", "Audits a pay-per-audit user runs per month", 3, 3, "audits / month", INT, True,
     "Owner estimate."),
    ("mix", "Share of users on the hobbyist plan", 0.4, 0.4, "%", PCT, True,
     "Owner estimate. The rest pay per audit."),
    ("data", "Data cost per audit", 0, 0, "$ / audit", USD_CENTS, False,
     "Public data: Yahoo Finance prices and earnings dates, DoltHub options data (implied vol). Free; cached after "
     "the first fetch."),
    ("fee_pct", "Payment fee, share of the charge", 0.029, 0.029, "%", PCT, False,
     "Stripe standard US card pricing: 2.9% + $0.30 per successful charge."),
    ("fee_fixed", "Payment fee, fixed per charge", 0.30, 0.30, "$ / charge", USD_CENTS, False,
     "Stripe standard US card pricing."),
    ("start_users", "Paying users at start", 0, 0, "users", INT, False, "Pre-launch."),
    ("new1", "New paying users in month 1", 10, 25, "users", INT, True,
     "Owner estimate. Base: organic from build-in-public posts. Growth: plus paid acquisition."),
    ("new_growth", "Monthly growth in new users", 0.05, 0.10, "% / month", PCT, True, "Owner estimate."),
    ("churn", "Monthly churn", 0.08, 0.06, "% / month", PCT, True,
     "Owner estimate, typical range for consumer subscriptions. Applied to both kinds of user."),
    ("cac", "Acquisition cost per new user (CAC)", 30, 40, "$ / user", USD, True,
     "Owner estimate. Growth spends more per user on paid channels."),
    ("hosting", "Hosting per month", 50, 50, "$ / month", USD, True,
     "Assumption: one small cloud VM (2 vCPU, 4 GB, about $25-50) for the web server and backtests, plus a domain. "
     "Backtests are code on cached data, so compute per audit is treated as part of this fixed cost."),
    ("neatlogs", "neatlogs per month", 0, 0, "$ / month", USD, True,
     "Placeholder: hackathon credits. Replace with the neatlogs plan price."),
    ("team", "Team cost per month", 2000, 6000, "$ / month", USD, True,
     "Owner estimate. Base: two part-time founders' stipend. Growth: adds one hire."),
    ("cash", "Starting cash", 25000, 25000, "$", USD, True, "Owner estimate: founder-funded."),
]
REF = {}            # key -> row on Assumptions
for i, (key, label, base, growth, unit, fmt, yellow, src) in enumerate(ROWS):
    r = 8 + i
    REF[key] = r
    A.cell(row=r, column=1, value=label).font = font()
    for col, val in ((2, base), (3, growth)):
        c = A.cell(row=r, column=col, value=val)
        c.number_format = fmt
        c.font = font(BLUE)
        if yellow:
            c.fill = YELLOW
    A.cell(row=r, column=4, value=unit).font = font(size=9)
    note(A.cell(row=r, column=5), src)
    A.row_dimensions[r].height = 30 if len(src) > 75 else 15
for col, width in zip("ABCDE", (44, 12, 12, 15, 90)):
    A.column_dimensions[col].width = width
A.freeze_panes = "A8"


def a(key, col):    # absolute reference to an assumption for a scenario column (B or C)
    if key == "llm":
        return "Assumptions!$B$5"
    return "Assumptions!$%s$%d" % (col, REF[key])


# ------------------------------------------------------------ cost estimate sheet
E = wb.create_sheet("Cost_Estimate")
E["A1"] = "LLM cost per audit: bottom-up ESTIMATE (not measured)"
E["A1"].font = font(RED, bold=True, size=13)
E["A2"] = ("How Assumptions!B5 was estimated before any real audit ran (AUDITOR_SPEC sections 8 and 13). "
           "Replace Assumptions!B5 with the measured figure after M2; this sheet then documents the estimate.")
E["A2"].font = font(italic=True, size=9)
header(E, 4, ["Input", "Value", "Unit", "Source or note"])


def enote(r, text):     # source notes on this sheet span D:J, so the call table below keeps narrow columns
    note(E.cell(row=r, column=4), text)
    E.merge_cells("D%d:J%d" % (r, r))


p_pro, p_flash = PRICES["deepseek-v4-pro"], PRICES["deepseek-flash"]
EST_INPUTS = [   # row 5..13
    ("deepseek-v4-pro input price (Planner, Naysayer; thinking on)", p_pro[0], "$ / 1M tokens", USD_CENTS,
     "src/llm.py PRICES, read at build time. DeepSeek peak, cache-miss rates: an upper bound; off-peak is half."),
    ("deepseek-v4-pro output price (thinking tokens billed as output)", p_pro[1], "$ / 1M tokens", USD_CENTS, "src/llm.py PRICES."),
    ("deepseek-flash input price (Reporter; thinking off)", p_flash[0], "$ / 1M tokens", USD_CENTS, "src/llm.py PRICES."),
    ("deepseek-flash output price", p_flash[1], "$ / 1M tokens", USD_CENTS, "src/llm.py PRICES."),
    ("Characters per token", CHARS_PER_TOKEN, "chars", INT, "Rule of thumb for English and JSON."),
    ("Completion tokens per thinking call (thinking + JSON reply)", THINKING_OUT, "tokens", INT,
     "ASSUMPTION: reasoning_effort high, so most of it is thinking; plausible range 1,500-4,000. "
     "The swarm's measured cost implies about 3,900 (sanity check below), so the estimate leans low if anything."),
    ("Completion tokens per Reporter call", REPORTER_OUT, "tokens", INT, "ASSUMPTION: 2 to 5 sentences of prose in JSON."),
    ("Chance the first plan is invalid (one Planner fix call)", P_INVALID, "%", PCT,
     "ASSUMPTION. The validator rejects off-menu features, ranges or groups; DeepSeek JSON mode does not enforce the schema."),
    ("Retry and contingency uplift", UPLIFT, "%", PCT,
     "Empty or off-schema replies are retried once inside llm(); the retry's tokens are billed (spec section 8)."),
]
for i, (label, val, unit, fmt, src) in enumerate(EST_INPUTS):
    r = 5 + i
    E.cell(row=r, column=1, value=label).font = font()
    c = E.cell(row=r, column=2, value=val)
    c.number_format = fmt
    c.font = font(BLUE)
    if "ASSUMPTION" in src:
        c.fill = YELLOW
    E.cell(row=r, column=3, value=unit).font = font(size=9)
    enote(r, src)

T0 = 16     # call table header row; calls on rows 17-21, total on 22
for i, h in enumerate(["Call", "Agent", "Model", "Expected calls per audit", "System prompt + schema (chars)",
                       "User prompt (chars)", "Prompt tokens", "Completion tokens", "Cost per call ($)",
                       "Expected cost per audit ($)", "Where the prompt size comes from"], 1):
    c = E.cell(row=T0, column=i, value=h)
    c.font = font(bold=True)
    c.fill = HEADER_FILL
    c.alignment = Alignment(wrap_text=True, vertical="top")
E.row_dimensions[T0].height = 42
for i, (label, agent, n, s, u, comp, src) in enumerate(CALLS):
    r = T0 + 1 + i
    flash = DS[agent] == "deepseek-flash"
    vals = [label, agent, DS[agent], n, s, u, "=(E{r}+F{r})/$B$9", "=$B$11" if flash else "=$B$10",
            "=G{r}*$B$%d/1000000+H{r}*$B$%d/1000000" % ((7, 8) if flash else (5, 6)),
            "=D{r}*I{r}"]
    for col, v in enumerate(vals, 1):
        v = v.format(r=r) if isinstance(v, str) else v
        cell = E.cell(row=r, column=col, value=v)
        typed = not (isinstance(v, str) and v.startswith("="))
        cell.font = font(BLUE if typed and col in (4, 5, 6) else BLACK)
        cell.number_format = {4: '0.0', 5: INT, 6: INT, 7: INT, 8: INT, 9: USD_MILLS, 10: USD_MILLS}.get(col, "General")
    note(E.cell(row=r, column=11), src)
    E.row_dimensions[r].height = 40
TOT = T0 + 1 + len(CALLS)       # 22
E.cell(row=TOT, column=1, value="Total").font = font(bold=True)
for col, f, fmt in ((4, "=SUM(D%d:D%d)" % (T0 + 1, TOT - 1), '0.0'), (10, "=SUM(J%d:J%d)" % (T0 + 1, TOT - 1), USD_MILLS)):
    c = E.cell(row=TOT, column=col, value=f)
    c.number_format = fmt
    c.font = font(bold=True)

R1 = TOT + 2    # 24: results block
P, F = T0 + 1, TOT - 1          # planner row, reporter (last) row
results = [
    ("Expected LLM calls per audit", "=D%d" % TOT, "calls", '0.0',
     "Spec section 4: Planner 1 (+1 only after an invalid plan), Naysayer 2, Reporter 1. Hard budget: 8 calls."),
    ("Cost per audit before uplift", "=J%d" % TOT, "$ / audit", USD_MILLS, ""),
    ("Estimated LLM cost per audit (ESTIMATE)", "=B%d*(1+B13)" % (R1 + 1), "$ / audit", USD_MILLS,
     "The bottom-up estimate. Rounded, it is the typed value of Assumptions!B5."),
    ("Assumptions!B5, the value the model uses", "=Assumptions!B5", "$ / audit", USD_MILLS,
     "Green link. Holds this estimate until M2, then the measured figure."),
    ("Difference: model input minus this estimate", "=B%d-B%d" % (R1 + 3, R1 + 2), "$ / audit", USD_MILLS,
     "Under $0.0005 while B5 is still the estimate (rounding)."),
    ("Worst case: all 8 budgeted calls (7 thinking + Reporter)", "=(7*I%d+I%d)*(1+B13)" % (P, F), "$ / audit", USD_MILLS,
     "Upper bound if every audit used the full budget."),
    ("Same estimate at DeepSeek off-peak rates (half price)", "=B%d/2" % (R1 + 2), "$ / audit", USD_MILLS, ""),
]
for i, (label, f, unit, fmt, src) in enumerate(results):
    r = R1 + i
    E.cell(row=r, column=1, value=label).font = font(bold="ESTIMATE" in label, color=RED if "ESTIMATE" in label else BLACK)
    c = E.cell(row=r, column=2, value=f)
    c.number_format = fmt
    c.font = font(GREEN if f.startswith("=Assumptions!") else BLACK, bold="ESTIMATE" in label)
    E.cell(row=r, column=3, value=unit).font = font(size=9)
    enote(r, src)
EST_ROW = R1 + 2                # 26

S0 = R1 + len(results) + 1      # 32: swarm sanity check
E.cell(row=S0, column=1, value="Sanity check: the trading swarm's measured cost").font = font(bold=True)
swarm = [
    ("Swarm LLM cost per decision, measured (upper bound)", 0.038, "$ / decision", USD_MILLS, True,
     "results/README.md: $11.76 logged over 310 validation setups on 2026-10-10, DeepSeek peak cache-miss prices."),
    ("deepseek-v4-pro thinking calls per swarm decision", 2, "calls", INT, True,
     "Two Planner rounds per setup (rounds = 2 on all 577 lines of results/swarm_validation.jsonl; Planner made "
     "1,154 of ~1,760 calls, docs/SWARM_SPEC.md section 15). Same model and thinking settings as the auditor."),
    ("Implied cost per thinking call", "=B%d/B%d" % (S0 + 1, S0 + 2), "$ / call", USD_MILLS, False,
     "Upper bound: treats the swarm's deepseek-flash Researcher call and rare Naysayer calls as free."),
    ("Bottom-up cost per thinking call (Planner row above)", "=I%d" % P, "$ / call", USD_MILLS, False, ""),
    ("Thinking calls per audit", '=SUMIF(C%d:C%d,"deepseek-v4-pro",D%d:D%d)' % (P, F, P, F), "calls", '0.0', False, ""),
    ("Swarm-calibrated cost per audit", "=B%d*B%d+J%d" % (S0 + 5, S0 + 3, F), "$ / audit", USD_MILLS, False,
     "Thinking calls per audit x the swarm's implied cost per thinking call, + the Reporter call."),
    ("Bottom-up estimate as a share of the swarm-calibrated figure", "=B%d/B%d" % (EST_ROW, S0 + 6), "x", '0.00"x"', False,
     "Below 1: the bottom-up estimate is lower than what the swarm's measured spend suggests. Same order of magnitude "
     "either way: a few cents per audit."),
]
for i, (label, v, unit, fmt, typed, src) in enumerate(swarm):
    r = S0 + 1 + i
    E.cell(row=r, column=1, value=label).font = font()
    c = E.cell(row=r, column=2, value=v)
    c.number_format = fmt
    c.font = font(BLUE if typed else BLACK)
    E.cell(row=r, column=3, value=unit).font = font(size=9)
    enote(r, src)

N0 = S0 + len(swarm) + 2
NOTES = [
    "Notes",
    "Calls follow the spec at M2 (section 4). M1 'before' runs make one Naysayer call (no follow-ups), so they "
    "should come in about one thinking call under this estimate. Update B5 from the M2 runs, as spec section 13 says.",
    "System prompt sizes are read from src/auditor/agents.py when this workbook is built: the system text plus the "
    "JSON-schema suffix src/llm.py appends for DeepSeek.",
    "User prompt sizes were measured on 2026-10-11 by running the audit loop with the fake LLM on the synthetic market of "
    "tests/test_auditor_run.py, extended to all 50 tickers, for the three demo ideas, then rounded up.",
    "Data costs $0 (Yahoo Finance, DoltHub, both public). Hosting is a fixed monthly cost on Assumptions, not per audit.",
    "To replace the estimate: type the mean measured cost per audit of the demo audits into Assumptions!B5. Source: "
    "section '9. Cost and trace' of each report.md (or cost.usd in state.json), cross-checked in neatlogs.",
]
for i, t in enumerate(NOTES):
    c = E.cell(row=N0 + i, column=1, value=t)
    c.font = font(bold=i == 0, size=9)
for col, width in zip("ABCDEFGHIJK", (52, 12, 14, 12, 14, 12, 11, 12, 12, 13, 70)):
    E.column_dimensions[col].width = width
for r in range(5, 14):
    E.row_dimensions[r].height = 30


# --------------------------------------------------------------- monthly models
MODEL_ROWS = {}     # line key -> row number on the model sheets


def build_model(title, col):
    ws = wb.create_sheet(title)
    ws["A1"] = "%s scenario: monthly model (months 1-%d)" % (title.split("_")[1], MONTHS)
    ws["A1"].font = font(bold=True, size=13)
    ws["A2"] = ("All values in $ unless the unit column says otherwise. Inputs live on the Assumptions sheet, column %s; "
                "LLM cost per audit is the single cell Assumptions!B5 (ESTIMATE)." % col)
    ws["A2"].font = font(italic=True, size=9)

    lines = [   # key, label, unit, first-month formula, later-month formula ({c} = column, {p} = previous column), format, color
        ("month", "Month", "", "1", "={p}{r_month}+1", INT, BLACK),
        None,
        ("users_start", "Paying users, start of month", "users", "=" + a("start_users", col), "={p}{r_users_end}", COUNT, None),
        ("new", "New users", "users", "=%s*(1+%s)^({c}{r_month}-1)" % (a("new1", col), a("new_growth", col)), None, COUNT, BLACK),
        ("churned", "Churned users", "users", "={c}{r_users_start}*%s" % a("churn", col), None, COUNT, BLACK),
        ("users_end", "Paying users, end of month", "users", "={c}{r_users_start}+{c}{r_new}-{c}{r_churned}", None, COUNT, BLACK),
        ("subs", "  on the hobbyist plan", "users", "={c}{r_users_end}*%s" % a("mix", col), None, COUNT, BLACK),
        ("ppa", "  paying per audit", "users", "={c}{r_users_end}-{c}{r_subs}", None, COUNT, BLACK),
        None,
        ("audits_sub", "Audits run by subscribers", "audits", "={c}{r_subs}*%s" % a("plan_used", col), None, COUNT, BLACK),
        ("audits_ppa", "Audits bought per audit", "audits", "={c}{r_ppa}*%s" % a("ppa_audits", col), None, COUNT, BLACK),
        ("audits", "Audits run", "audits", "={c}{r_audits_sub}+{c}{r_audits_ppa}", None, COUNT, BLACK),
        None,
        ("rev_sub", "Revenue: hobbyist plan", "$", "={c}{r_subs}*%s" % a("plan_price", col), None, USD, BLACK),
        ("rev_ppa", "Revenue: pay per audit", "$", "={c}{r_audits_ppa}*%s" % a("price_audit", col), None, USD, BLACK),
        ("revenue", "Revenue", "$", "={c}{r_rev_sub}+{c}{r_rev_ppa}", None, USD, BLACK),
        ("fees", "Payment fees", "$",
         "={c}{r_subs}*(%s*%s+%s)+{c}{r_audits_ppa}*(%s*%s+%s/%s)" % (
             a("plan_price", col), a("fee_pct", col), a("fee_fixed", col),
             a("price_audit", col), a("fee_pct", col), a("fee_fixed", col), a("pack", col)), None, USD, BLACK),
        ("llm", "LLM inference (audits x cost per audit)", "$", "={c}{r_audits}*%s" % a("llm", col), None, USD, BLACK),
        ("data", "Data (audits x data cost per audit)", "$", "={c}{r_audits}*%s" % a("data", col), None, USD, BLACK),
        ("gross", "Gross profit", "$", "={c}{r_revenue}-{c}{r_fees}-{c}{r_llm}-{c}{r_data}", None, USD, BLACK),
        ("gm", "Gross margin", "%", "=IF({c}{r_revenue}=0,0,{c}{r_gross}/{c}{r_revenue})", None, PCT, BLACK),
        None,
        ("marketing", "Marketing (new users x CAC)", "$", "={c}{r_new}*%s" % a("cac", col), None, USD, BLACK),
        ("hosting", "Hosting", "$", "=" + a("hosting", col), None, USD, GREEN),
        ("neatlogs", "neatlogs", "$", "=" + a("neatlogs", col), None, USD, GREEN),
        ("team", "Team", "$", "=" + a("team", col), None, USD, GREEN),
        ("op", "Operating profit", "$", "={c}{r_gross}-{c}{r_marketing}-{c}{r_hosting}-{c}{r_neatlogs}-{c}{r_team}", None, USD, BLACK),
        None,
        ("cash_start", "Cash, start of month", "$", "=" + a("cash", col), "={p}{r_cash_end}", USD, None),
        ("cash_end", "Cash, end of month", "$", "={c}{r_cash_start}+{c}{r_op}", None, USD, BLACK),
        None,
        ("flag_cash", "Flag: cash below zero (1 = yes)", "flag", "=IF({c}{r_cash_end}<0,1,0)", None, INT, BLACK),
        ("flag_profit", "Flag: operating profit at or above zero (1 = yes)", "flag", "=IF({c}{r_op}>=0,1,0)", None, INT, BLACK),
    ]
    r = 4
    rows = {}
    for line in lines:
        if line:
            rows[line[0]] = r
        r += 1
    MODEL_ROWS.update(rows)
    names = {"r_" + k: v for k, v in rows.items()}

    ws.cell(row=3, column=1, value="Line").font = font(bold=True)
    ws.cell(row=3, column=2, value="Unit").font = font(bold=True)
    for line in lines:
        if not line:
            continue
        key, label, unit, first, later, fmt, color = line
        rr = rows[key]
        ws.cell(row=rr, column=1, value=label).font = font(bold=key in ("users_end", "audits", "revenue", "gross", "op", "cash_end"))
        ws.cell(row=rr, column=2, value=unit).font = font(size=9)
        for m in range(MONTHS):
            colno = FIRST_COL + m
            c_letter = get_column_letter(colno)
            p_letter = get_column_letter(colno - 1)
            tmpl = first if (m == 0 or later is None) else later
            value = tmpl.format(c=c_letter, p=p_letter, **names)
            cell = ws.cell(row=rr, column=colno, value=int(value) if value.isdigit() else value)
            cell.number_format = fmt
            if key == "month":
                cell.font = font(BLUE if m == 0 else BLACK, bold=True)
                cell.fill = HEADER_FILL
            else:
                link = value.startswith("=Assumptions!") or (color is None and m == 0)
                cell.font = font(GREEN if link else BLACK)
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 10
    for m in range(MONTHS):
        ws.column_dimensions[get_column_letter(FIRST_COL + m)].width = 11
    ws.freeze_panes = "C5"
    return ws


build_model("Model_Base", "B")
build_model("Model_Growth", "C")
R = MODEL_ROWS

# -------------------------------------------------------------- unit economics
U = wb.create_sheet("Unit_Economics")
U["A1"] = "Unit economics: per audit and per subscriber"
U["A1"].font = font(bold=True, size=13)
U["A2"] = "LLM cost per audit is Assumptions!B5 (ESTIMATE until M2 measures it)."
U["A2"].font = font(italic=True, size=9)
header(U, 3, ["Line", "Base", "Growth", "Unit"])
s = "{s}"
ue = [   # label, formula template ({s} = scenario column on Assumptions, {c} = this column), unit, format
    ("One audit, pay per audit", None, None, None),
    ("Price per audit", "=" + a("price_audit", s), "$ / audit", USD_CENTS),                                        # 5
    ("Payment fees per audit", "=%s*%s+%s/%s" % (a("price_audit", s), a("fee_pct", s), a("fee_fixed", s), a("pack", s)),
     "$ / audit", USD_CENTS),                                                                                     # 6
    ("LLM cost per audit (ESTIMATE)", "=" + a("llm", s), "$ / audit", USD_MILLS),                                 # 7
    ("Data cost per audit", "=" + a("data", s), "$ / audit", USD_CENTS),                                          # 8
    ("Contribution per audit", "={c}5-{c}6-{c}7-{c}8", "$ / audit", USD_CENTS),                                   # 9
    ("Gross margin per audit", "=IF({c}5=0,0,{c}9/{c}5)", "%", PCT),                                              # 10
    ("LLM cost per audit at which contribution is zero", "={c}5-{c}6-{c}8", "$ / audit", USD_CENTS),              # 11
    ("One hobbyist subscriber, per month", None, None, None),                                                     # 12
    ("Plan price", "=" + a("plan_price", s), "$ / month", USD_CENTS),                                             # 13
    ("Payment fees", "=%s*%s+%s" % (a("plan_price", s), a("fee_pct", s), a("fee_fixed", s)), "$ / month", USD_CENTS),  # 14
    ("LLM cost (audits run x cost per audit)", "=%s*%s" % (a("plan_used", s), a("llm", s)), "$ / month", USD_CENTS),    # 15
    ("Data cost", "=%s*%s" % (a("plan_used", s), a("data", s)), "$ / month", USD_CENTS),                          # 16
    ("Contribution per subscriber", "={c}13-{c}14-{c}15-{c}16", "$ / month", USD_CENTS),                          # 17
    ("Gross margin per subscriber", "=IF({c}13=0,0,{c}17/{c}13)", "%", PCT),                                      # 18
    ("Contribution if all included audits are used", "={c}13-{c}14-%s*(%s+%s)" % (a("plan_audits", s), a("llm", s), a("data", s)),
     "$ / month", USD_CENTS),                                                                                     # 19
    ("Revenue per audit actually run on the plan", "=IF(%s=0,0,{c}13/%s)" % (a("plan_used", s), a("plan_used", s)),
     "$ / audit", USD_CENTS),                                                                                     # 20
    ("One paying user, blended, per month", None, None, None),                                                    # 21
    ("Contribution per pay-per-audit user", "=%s*{c}9" % a("ppa_audits", s), "$ / month", USD_CENTS),             # 22
    ("Blended contribution per user", "=%s*{c}17+(1-%s)*{c}22" % (a("mix", s), a("mix", s)), "$ / month", USD_CENTS),  # 23
    ("Acquisition cost (CAC)", "=" + a("cac", s), "$ / user", USD),                                               # 24
    ("CAC payback", '=IF({c}23<=0,"n/a",{c}24/{c}23)', "months", "0.0"),                                          # 25
    ("Lifetime value (LTV)", '=IF(%s=0,"n/a",{c}23/%s)' % (a("churn", s), a("churn", s)), "$", USD),              # 26
    ("LTV to CAC", '=IF({c}24=0,"n/a",{c}26/{c}24)', "x", '0.0"x"'),                                              # 27
]
for i, (label, tmpl, unit, fmt) in enumerate(ue):
    r = 4 + i
    section = tmpl is None
    U.cell(row=r, column=1, value=label).font = font(bold=section or label in ("Contribution per audit", "Contribution per subscriber", "LTV to CAC"))
    if section:
        continue
    for col, scen in ((2, "B"), (3, "C")):
        v = tmpl.format(s=scen, c=get_column_letter(col))
        cell = U.cell(row=r, column=col, value=v)
        cell.number_format = fmt
        cell.font = font(GREEN if v.startswith("=Assumptions!") and not any(op in v[1:] for op in "*/+-") else BLACK)
    U.cell(row=r, column=4, value=unit).font = font(size=9)
U["A29"] = ("LTV = blended contribution per user / monthly churn. Payback = CAC / blended contribution. "
            "Contribution counts payment fees, LLM and data; hosting, neatlogs and team are fixed costs on the model sheets.")
U["A29"].font = font(italic=True, size=9)
U.column_dimensions["A"].width = 48
for col in "BC":
    U.column_dimensions[col].width = 13
U.column_dimensions["D"].width = 14

# ---------------------------------------------------------------------- summary
S = wb.create_sheet("Summary", 0)
S["A1"] = "Strategy Auditor: business plan summary"
S["A1"].font = font(bold=True, size=13)
S["A2"] = ("Two scenarios over %d months, priced per audit. Change inputs on the Assumptions sheet; everything here "
           "recalculates. LLM cost per audit is an ESTIMATE (Assumptions!B5) until M2 measures it." % MONTHS)
S["A2"].font = font(italic=True, size=9)
header(S, 4, ["Metric", "Base", "Growth", "Unit"])
summary = [
    ("LLM cost per audit (ESTIMATE, Assumptions!B5)", "=Assumptions!$B$5", "$ / audit", USD_MILLS),          # 5
    ("Contribution per audit, pay per audit", "=Unit_Economics!{u}9", "$ / audit", USD_CENTS),                # 6
    ("Gross margin per audit", "=Unit_Economics!{u}10", "%", PCT),                                            # 7
    ("Contribution per hobbyist subscriber", "=Unit_Economics!{u}17", "$ / month", USD_CENTS),                # 8
    ("Gross margin per subscriber", "=Unit_Economics!{u}18", "%", PCT),                                       # 9
    ("LTV to CAC (blended)", "=Unit_Economics!{u}27", "x", '0.0"x"'),                                         # 10
    ("Paying users, month 6", "={m}!%s%d" % (M6, R["users_end"]), "users", COUNT),                            # 11
    ("Paying users, month %d" % MONTHS, "={m}!%s%d" % (LAST, R["users_end"]), "users", COUNT),                # 12
    ("Audits run, month %d" % MONTHS, "={m}!%s%d" % (LAST, R["audits"]), "audits", COUNT),                    # 13
    ("Revenue, month %d" % MONTHS, "={m}!%s%d" % (LAST, R["revenue"]), "$ / month", USD),                    # 14
    ("Gross margin, month %d" % MONTHS, "={m}!%s%d" % (LAST, R["gm"]), "%", PCT),                            # 15
    ("Revenue, months 1-%d" % MONTHS, "=SUM({m}!C%d:%s%d)" % (R["revenue"], LAST, R["revenue"]), "$", USD),   # 16
    ("LLM cost, months 1-%d" % MONTHS, "=SUM({m}!C%d:%s%d)" % (R["llm"], LAST, R["llm"]), "$", USD),          # 17
    ("Operating profit, months 1-%d" % MONTHS, "=SUM({m}!C%d:%s%d)" % (R["op"], LAST, R["op"]), "$", USD),    # 18
    ("Lowest cash balance", "=MIN({m}!C%d:%s%d)" % (R["cash_end"], LAST, R["cash_end"]), "$", USD),           # 19
    ("Cash, end of month %d" % MONTHS, "={m}!%s%d" % (LAST, R["cash_end"]), "$", USD),                       # 20
    ("Runway: first month cash goes below zero",                                                              # 21
     '=IF(SUM({m}!C%d:%s%d)=0,"none within %d months",MATCH(1,{m}!C%d:%s%d,0))' % (
         R["flag_cash"], LAST, R["flag_cash"], MONTHS, R["flag_cash"], LAST, R["flag_cash"]), "month", INT),
    ("Runway left after month %d at that month's burn" % MONTHS,                                              # 22
     '=IF({m}!%s%d>=0,"not burning cash",MAX(0,{m}!%s%d/-{m}!%s%d))' % (LAST, R["op"], LAST, R["cash_end"], LAST, R["op"]),
     "months", "0.0"),
    ("Break-even: first month of operating profit",                                                          # 23
     '=IF(SUM({m}!C%d:%s%d)=0,"not within %d months",MATCH(1,{m}!C%d:%s%d,0))' % (
         R["flag_profit"], LAST, R["flag_profit"], MONTHS, R["flag_profit"], LAST, R["flag_profit"]), "month", INT),
    ("Funding needed to never go below zero", "=MAX(0,-MIN({m}!C%d:%s%d))" % (R["cash_end"], LAST, R["cash_end"]), "$", USD),  # 24
]
for i, (label, tmpl, unit, fmt) in enumerate(summary):
    r = 5 + i
    S.cell(row=r, column=1, value=label).font = font(RED if "ESTIMATE" in label else BLACK, bold="ESTIMATE" in label)
    for col, m, u in ((2, "Model_Base", "B"), (3, "Model_Growth", "C")):
        cell = S.cell(row=r, column=col, value=tmpl.format(m=m, u=u))
        cell.number_format = fmt
        cell.font = font(GREEN if tmpl.startswith(("={m}!", "=Unit", "=Assumptions")) else BLACK)
    S.cell(row=r, column=4, value=unit).font = font(size=9)
notes = [
    "How to read this:",
    "- One audit = one trading idea in, one evidence-backed verdict out. Sold per audit ($2, in packs of 5) or as a "
    "hobbyist plan ($15/month, 20 audits): both are pricing hypotheses.",
    "- LLM cost per audit is a bottom-up ESTIMATE from the code (Cost_Estimate sheet), at DeepSeek peak prices. "
    "It is replaced with the measured figure after M2.",
    "- Variable cost is a few cents an audit, so margins are set by price and card fees; the plan is decided by "
    "users, churn, CAC and team cost (owner estimates, yellow on Assumptions).",
    "- No fees or taxes beyond card processing are modeled. The auditor gives research verdicts, not financial advice.",
]
for i, t in enumerate(notes):
    c = S.cell(row=27 + i, column=1, value=t)
    c.font = font(bold=i == 0, size=9)
S.column_dimensions["A"].width = 50
for col in "BC":
    S.column_dimensions[col].width = 22
S.column_dimensions["D"].width = 12

wb.save(OUT)
print("saved", OUT, "| estimate %.5f -> Assumptions!B5 = %.3f" % (ESTIMATE, LLM_INPUT),
      "| model rows:", {k: R[k] for k in ("users_end", "audits", "revenue", "llm", "op", "cash_end", "flag_cash", "flag_profit")})
