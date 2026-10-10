"""neatlogs tracing for the swarm.

Every LLM call, tool call, and agent step runs inside Tracer.span(). Spans nest under the
span that is open when they start, and carry agent/round/ticker/date tags. Spans are
recorded through neatlogs' tracker by hand, because neatlogs only auto-patches
client.messages.create and the swarm also uses client.beta.messages.create.

Without NEATLOGS_API_KEY, spans are kept in Tracer.spans only and nothing is sent.
"""
import contextlib
import json
import os
import time

from neatlogs.core import current_span_id_context


class Tracer:
    def __init__(self, tracker=None):
        self.tracker = tracker
        self.spans = []     # local copy of every span, for summaries and tests

    @contextlib.contextmanager
    def span(self, kind, name, model=None, **tags):
        """Open a span. The yielded dict takes input, output, token counts, and cost."""
        rec = {"kind": kind, "name": name, "model": model, "tags": tags, "input": None,
               "output": None, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        nl = token = None
        if self.tracker:
            nl = self.tracker.start_llm_span(model=model, provider="anthropic" if model else "local",
                                             node_type=kind, node_name=name)
            nl.tags = list(nl.tags) + ["%s:%s" % kv for kv in tags.items()]
            token = current_span_id_context.set(nl.span_id)   # children nest under this span
        start, error = time.time(), None
        try:
            yield rec
        except Exception as e:
            error = e
            raise
        finally:
            rec["duration"] = time.time() - start
            rec["status"] = "FAILURE" if error else "SUCCESS"
            self.spans.append(rec)
            if nl:
                current_span_id_context.reset(token)
                nl.messages = [{"role": "user", "content": _text(rec["input"])}]
                nl.completion = _text(rec["output"])
                nl.prompt_tokens = rec["prompt_tokens"]
                nl.completion_tokens = rec["completion_tokens"]
                nl.total_tokens = rec["prompt_tokens"] + rec["completion_tokens"]
                nl.cost = rec["cost"]
                self.tracker.end_llm_span(nl, success=error is None, error=error)

    def total_cost(self):
        return sum(s["cost"] for s in self.spans)


def _text(value):
    return value if isinstance(value, str) else json.dumps(value, default=str)


def make_tracer(tags=("trading-swarm",)):
    key = os.environ.get("NEATLOGS_API_KEY")
    if not key:
        print("NEATLOGS_API_KEY not set: spans are kept locally only, nothing is sent to neatlogs.")
        return Tracer()
    import neatlogs
    return Tracer(neatlogs.init(api_key=key, tags=list(tags)))
