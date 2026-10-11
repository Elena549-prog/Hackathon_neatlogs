"""Strategy Auditor CLI (AUDITOR_SPEC section 9).

    python -m src.auditor "buy straddles on tech stocks before earnings"
    python -m src.auditor --id <audit_id> "<idea>"            # used by the server (section 16)
    python -m src.auditor --resume <audit_id>
    python -m src.auditor --fault dolthub_timeout "<idea>"    # or --fault llm_empty (section 6)
    python -m src.auditor --provider fake "<idea>"            # keyword fake LLM: development only

DeepSeek runs refuse to start when the account balance is below $2 (section 8).
"""
import argparse
import datetime as dt
import json
import os
import secrets
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .data import IV_END, _fetch_window, _http_query, fetch_earnings, fetch_implied_vol, fetch_prices
from .fake_llm import EmptyFirstReply, make_fake_llm
from .run import run_audit

REPO = Path(__file__).resolve().parents[2]
BALANCE_URL = "https://api.deepseek.com/user/balance"
MIN_BALANCE = 2.0


def _http_get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def deepseek_balance(get=None):
    """Total USD balance from DeepSeek's balance API, or None when the key is missing or the call fails."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    try:
        d = (get or _http_get_json)(BALANCE_URL, {"Authorization": "Bearer " + key})
        return float(d["balance_infos"][0]["total_balance"])
    except Exception:
        return None


def make_fetchers(fault):
    """The real data tools. `--fault dolthub_timeout` probes one DoltHub window with a query that times out once,
    so the retry (and its recovered event) is real even when the implied-vol cache is already warm."""
    def iv(tickers, cache_dir, on_recovered=None, fault_first_timeout=False, **kw):
        if fault_first_timeout:
            state = {"fired": False}

            def probe(sql):
                if not state["fired"]:
                    state["fired"] = True
                    raise TimeoutError("injected DoltHub timeout")
                return _http_query(sql)

            b = pd.Timestamp(IV_END)
            _fetch_window(list(tickers), b - pd.Timedelta(days=13), b, probe, time.sleep, on_recovered)
        return fetch_implied_vol(tickers, cache_dir, on_recovered=on_recovered)

    return {"prices": fetch_prices, "iv": iv, "earnings": fetch_earnings}


def new_audit_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m src.auditor", description=__doc__.splitlines()[0])
    ap.add_argument("idea", nargs="?", help="the trading idea in plain English")
    ap.add_argument("--id", dest="audit_id", help="audit id (default: timestamp)")
    ap.add_argument("--resume", metavar="AUDIT_ID", help="continue an interrupted audit")
    ap.add_argument("--fault", choices=["dolthub_timeout", "llm_empty"], help="inject one failure (labelled INJECTED)")
    ap.add_argument("--provider", default="deepseek", choices=["deepseek", "claude", "fake"])
    ap.add_argument("--no-balance-check", action="store_true", help="skip the DeepSeek balance check")
    ap.add_argument("--root", default=str(REPO / "runs" / "audits"))
    ap.add_argument("--cache", default=str(REPO / "data" / "cache"))
    args = ap.parse_args(argv)
    if not args.idea and not args.resume:
        ap.error("give an idea, or --resume <audit_id>")

    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env")
    except ImportError:
        pass

    if args.fault == "llm_empty" and args.provider != "deepseek":
        print("--fault llm_empty is only wired for the deepseek provider (it blanks the first real reply); "
              "nothing would be injected with --provider %s." % args.provider)
        return 2

    if args.provider == "deepseek" and not args.no_balance_check:
        balance = deepseek_balance()
        if balance is None:
            print("DeepSeek balance unknown (no DEEPSEEK_API_KEY or the balance API failed). Check it by hand and "
                  "re-run with --no-balance-check, or use --provider fake for development.")
            return 2
        if balance < MIN_BALANCE:
            print("DeepSeek balance $%.2f is below $%.2f: top up before a real audit (section 8)." % (balance, MIN_BALANCE))
            return 2

    from src.tracing import make_tracer
    tracer = make_tracer(tags=("strategy-auditor", "provider:" + args.provider))
    if args.provider == "fake":
        llm = make_fake_llm(tracer)
    else:
        from src.llm import make_llm
        client = None
        if args.fault == "llm_empty":
            from openai import OpenAI
            client = EmptyFirstReply(OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com"))
        llm = make_llm(tracer, args.provider, client)

    audit_id = args.resume or args.audit_id or new_audit_id()
    out = run_audit(args.idea or "", audit_id, llm, tracer, root=Path(args.root), cache_dir=Path(args.cache),
                    fetchers=make_fetchers(args.fault), fault=args.fault, resume=bool(args.resume), provider=args.provider)
    tracer.flush()
    v = out["verdict"]
    print("audit %s" % audit_id)
    print("verdict: %s (%s)" % (v["verdict"], v["reason"]))
    print("report: %s" % out["report_path"])
    print("events: %s" % out["events_path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
