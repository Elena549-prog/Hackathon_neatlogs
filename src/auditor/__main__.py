"""Strategy Auditor CLI (spec section 9).

    python -m src.auditor "buy straddles on tech stocks before earnings"
    python -m src.auditor --id <audit_id> "<idea>"          # used by the server (section 16)
    python -m src.auditor --resume <audit_id>
    python -m src.auditor --fault dolthub_timeout "<idea>"  # or --fault llm_empty
    python -m src.auditor --no-followups "<idea>"           # M1 ("before") runs

Keys come from the environment: DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY with --provider claude),
NEATLOGS_API_KEY for tracing. Before a real DeepSeek audit the account balance is checked
(https://api.deepseek.com/user/balance) and the audit refuses to start below $2.
"""
import argparse
import json
import os
import shutil
import sys
import urllib.request
from types import SimpleNamespace

MIN_BALANCE_USD = 2.0


def deepseek_balance():
    """USD balance from DeepSeek's balance API, or None if it can't be read."""
    req = urllib.request.Request("https://api.deepseek.com/user/balance",
                                 headers={"Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"],
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.load(r)
        usd = [b for b in d.get("balance_infos", []) if b.get("currency") == "USD"]
        return float(usd[0]["total_balance"]) if usd else None
    except Exception:
        return None


class EmptyOnce:
    """OpenAI-style client whose first completion is empty (fault llm_empty), then the real client."""

    def __init__(self, client, fired):
        self._client, self._fired, self._armed = client, fired, True
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        if self._armed:
            self._armed = False
            self._fired.append(True)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""), finish_reason="stop")],
                                   usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0))
        return self._client.chat.completions.create(**kwargs)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m src.auditor")
    ap.add_argument("idea", nargs="?")
    ap.add_argument("--id")
    ap.add_argument("--resume", metavar="AUDIT_ID")
    ap.add_argument("--fault", choices=["dolthub_timeout", "llm_empty"])
    ap.add_argument("--provider", default="deepseek", choices=["deepseek", "claude"])
    ap.add_argument("--no-followups", action="store_true", help="M1 'before' run: no Naysayer follow-ups")
    ap.add_argument("--no-reporter", action="store_true")
    ap.add_argument("--save-demo", action="store_true", help="copy events, report and state to results/audits/")
    ap.add_argument("--skip-balance-check", action="store_true")
    args = ap.parse_args(argv)
    if not args.resume and not args.idea:
        ap.error("give an idea, or --resume <audit_id>")

    from src.tracing import make_tracer
    tracer = make_tracer(tags=("strategy-auditor",), workflow_name="strategy-auditor")   # before the SDK imports

    if args.provider == "deepseek" and not args.skip_balance_check:
        bal = deepseek_balance()
        if bal is None:
            print("Could not read the DeepSeek balance; check it by hand (docs/STATUS.md, Running things).")
        elif bal < MIN_BALANCE_USD:
            sys.exit("DeepSeek balance $%.2f is below $%.2f; top up before a real audit." % (bal, MIN_BALANCE_USD))

    from src.llm import make_llm
    from src.auditor.audit import Audit, new_id

    fired = []
    client = None
    if args.fault == "llm_empty":
        if args.provider != "deepseek":
            sys.exit("--fault llm_empty is implemented for the DeepSeek provider")
        from openai import OpenAI
        client = EmptyOnce(OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com"), fired)
    llm = make_llm(tracer, args.provider, client)
    llm.fault_fired = fired

    audit_id = args.resume or args.id or new_id()
    audit = Audit(audit_id, llm, tracer, followups=not args.no_followups, use_reporter=not args.no_reporter)
    state = audit.resume() if args.resume else audit.start(args.idea, fault=args.fault)

    v = state["verdict"]
    print("\nAudit %s: %s. %s" % (audit_id, v["verdict"].upper(), v["reason"]))
    print("Report: %s" % os.path.join(audit.dir, "report.md"))
    print("LLM calls %d, cost $%.4f" % (state["llm"]["calls"], state["llm"]["cost_usd"]))
    if args.save_demo:
        dest = os.path.join("results", "audits", audit_id)
        os.makedirs(dest, exist_ok=True)
        for name in ("events.jsonl", "report.md", "state.json"):
            shutil.copy(os.path.join(audit.dir, name), os.path.join(dest, name))
        print("Copied to %s" % dest)


if __name__ == "__main__":
    main()
