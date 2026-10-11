"""neatlogs tracing for the swarm (neatlogs 1.4, OpenTelemetry / OpenInference).

Workflow, agent, and tool steps run inside Tracer.span(). Each becomes a neatlogs span with an
OpenInference kind, `tag.tags` (agent/round/ticker/date), and input/output values. Spans nest
under the span open when they start, so each setup is one trace. LLM calls are recorded by
neatlogs' own OpenAI/Anthropic instrumentation, nested under the agent span that made them.

Tracer.spans keeps a local copy of every span, with our token and cost counts, for summaries
and tests. Without NEATLOGS_API_KEY nothing is sent.
"""
import contextlib
import json
import os
import time

KINDS = {"workflow": "WORKFLOW", "agent": "AGENT", "llm": "AGENT", "tool": "TOOL"}


class Tracer:
    def __init__(self, open_span=None, flush=None, on_span=None):
        """open_span(name, kind=..., **attributes) is a context manager yielding an OTel span
        (neatlogs.trace in production). Without it, spans are kept locally only.
        on_span(rec) is called when a span ends (the auditor turns llm spans into events)."""
        self.open_span = open_span
        self._flush = flush
        self.on_span = on_span
        self.spans = []

    @contextlib.contextmanager
    def span(self, kind, name, model=None, **tags):
        """Open a span. The yielded dict takes input, output, token counts, and cost."""
        rec = {"kind": kind, "name": name, "model": model, "tags": tags, "input": None,
               "output": None, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        attributes = {"tag.tags": ["%s:%s" % kv for kv in tags.items()]}
        opened = self.open_span(name, kind=KINDS[kind], **attributes) if self.open_span else contextlib.nullcontext()
        start, error = time.time(), None
        with opened as otel_span:
            try:
                yield rec
            except Exception as e:
                error = e
                if otel_span is not None:
                    from opentelemetry.trace import Status, StatusCode
                    otel_span.record_exception(e)
                    otel_span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            finally:
                rec["duration"] = time.time() - start
                rec["status"] = "FAILURE" if error else "SUCCESS"
                self.spans.append(rec)
                if otel_span is not None:
                    _annotate(otel_span, rec)
                if self.on_span is not None:
                    try:
                        self.on_span(rec)
                    except Exception:   # a listener must never mask the span's own outcome
                        pass

    def total_cost(self):
        return sum(s["cost"] for s in self.spans)

    def flush(self):
        if self._flush:
            self._flush()


def _annotate(otel_span, rec):
    for key in ("input", "output"):
        if rec[key] is not None:
            otel_span.set_attribute("%s.value" % key, _text(rec[key]))
    if rec["model"]:
        otel_span.set_attribute("metadata", json.dumps({
            "model": rec["model"], "prompt_tokens": rec["prompt_tokens"],
            "completion_tokens": rec["completion_tokens"], "cost_usd_upper_bound": rec["cost"]}))


def _text(value):
    return value if isinstance(value, str) else json.dumps(value, default=str)


def make_tracer(tags=("trading-swarm",)):
    """Call before the OpenAI/Anthropic SDKs are imported, so neatlogs can instrument them."""
    key = os.environ.get("NEATLOGS_API_KEY")
    if not key:
        print("NEATLOGS_API_KEY not set: spans are kept locally only, nothing is sent to neatlogs.")
        return Tracer()
    import neatlogs
    neatlogs.init(api_key=key, workflow_name="trading-swarm", tags=list(tags),
                  instrumentations=["openai", "anthropic"])
    return Tracer(neatlogs.trace, neatlogs.flush)
