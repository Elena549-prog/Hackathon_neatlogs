"""One LLM call that returns a JSON object, recorded as a neatlogs span.

Agents call llm(agent, system, prompt, schema, **tags) and never pick a model; the
provider decides. DeepSeek is the default; Claude is kept as an alternative.

DeepSeek's JSON mode guarantees valid JSON but not the schema, so the reply is checked
against the schema's required keys and types here. Empty or off-schema replies are
retried once, then raise LLMError (DeepSeek documents occasional empty replies).
"""
import json
import os


MODELS = {
    "deepseek": {"researcher": "deepseek-flash", "planner": "deepseek-v4-pro", "naysayer": "deepseek-v4-pro",
                 "reporter": "deepseek-flash"},
    "claude": {"researcher": "claude-haiku-5-5", "planner": "claude-sonnet-5-5", "naysayer": "claude-sonnet-5-5",
               "reporter": "claude-haiku-5-5"},
}
# $ per 1M tokens (input, output). ponytail: DeepSeek at peak, cache-miss rates, so cost is an upper bound.
PRICES = {"deepseek-flash": (0.30, 1.20), "deepseek-v4-pro": (1.32, 3.96),
          "claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}
DEEPSEEK_THINKING = {"researcher": False, "planner": True, "naysayer": True, "reporter": False}
CLAUDE_EFFORT = {"claude-haiku-5-5": "low", "claude-sonnet-5-5": "medium"}
ATTEMPTS = 2

JSON_TYPES = {"string": str, "number": (int, float), "integer": int, "array": list, "object": dict}


class LLMError(Exception):
    pass


def schema_error(out, schema):
    """None if `out` has every required key with the right top-level type, else the reason."""
    if not isinstance(out, dict):
        return "reply is not a JSON object"
    for key in schema["required"]:
        if key not in out:
            return "missing key %r" % key
        want = schema["properties"][key]["type"]
        value = out[key]
        if isinstance(value, bool) or not isinstance(value, JSON_TYPES[want]):
            return "key %r should be %s" % (key, want)
    return None


def make_llm(tracer, provider="deepseek", client=None):
    if provider == "deepseek":
        call = _deepseek_call(client)
    elif provider == "claude":
        call = _claude_call(client)
    else:
        raise ValueError("unknown provider %r" % provider)

    def llm(agent, system, prompt, schema, **tags):
        model = MODELS[provider][agent]
        with tracer.span("llm", agent, model=model, agent=agent, **tags) as rec:
            rec["input"] = prompt
            problem = None
            for attempt in range(1, ATTEMPTS + 1):
                text, tokens_in, tokens_out, stop = call(agent, model, system, prompt, schema)
                price_in, price_out = PRICES[model]
                rec["prompt_tokens"] += tokens_in
                rec["completion_tokens"] += tokens_out
                rec["cost"] += (tokens_in * price_in + tokens_out * price_out) / 1e6
                rec["output"] = text
                if stop in ("refusal", "max_tokens", "length", "content_filter"):
                    raise LLMError("%s stopped with %s" % (agent, stop))
                try:
                    out = json.loads(text) if text else None
                    problem = "empty reply" if out is None else schema_error(out, schema)
                except json.JSONDecodeError as e:
                    problem = "invalid JSON: %s" % e
                if problem is None:
                    rec["attempts"] = attempt
                    return out
            raise LLMError("%s: %s after %d attempts" % (agent, problem, ATTEMPTS))

    return llm


def _deepseek_call(client):
    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

    def call(agent, model, system, prompt, schema):
        thinking = DEEPSEEK_THINKING[agent]
        kwargs = dict(
            model=model, max_tokens=16000,
            messages=[{"role": "system", "content": system + "\n\nReply with one JSON object that matches "
                       "this JSON schema, and nothing else:\n" + json.dumps(schema)},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}},
        )
        if thinking:
            kwargs["reasoning_effort"] = "high"
        resp = client.chat.completions.create(**kwargs)   # neatlogs' OpenAI instrumentation records this call
        choice = resp.choices[0]
        return choice.message.content, resp.usage.prompt_tokens, resp.usage.completion_tokens, choice.finish_reason

    return call


def _claude_call(client):
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    def call(agent, model, system, prompt, schema):
        kwargs = dict(model=model, max_tokens=16000, system=system,
                      messages=[{"role": "user", "content": prompt}],
                      output_config={"effort": CLAUDE_EFFORT[model],
                                     "format": {"type": "json_schema", "schema": schema}})
        if model == "claude-sonnet-5-5":
            # Server-side fallback: if the model declines, the API re-runs the request on another model.
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                               fallbacks="default", **kwargs)
        else:
            resp = client.messages.create(**kwargs)
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return text, resp.usage.input_tokens, resp.usage.output_tokens, resp.stop_reason

    return call
