"""LLM wrapper: DeepSeek request shape, schema checks, retries, neatlogs de-duplication, Claude path."""
import json

import pytest

from src.agents import naysayer, planner, researcher
from src.llm import LLMError, make_llm, schema_error
from src.tracing import Tracer
from tests.helpers import PLAN_OUT, FakeClient, FakeDeepSeekClient


def call(agent_module, name, client, provider="deepseek", tracer=None):
    llm = make_llm(tracer or Tracer(), provider, client)
    return llm(name, agent_module.SYSTEM, "{}", agent_module.SCHEMA, round=1)


def test_deepseek_request_shape_per_agent():
    client = FakeDeepSeekClient()
    call(researcher, "researcher", client)
    call(planner, "planner", client)
    r, p = client.requests
    assert (r["model"], p["model"]) == ("deepseek-flash", "deepseek-v4-pro")
    assert r["response_format"] == p["response_format"] == {"type": "json_object"}
    assert r["extra_body"] == {"thinking": {"type": "disabled"}} and "reasoning_effort" not in r
    assert p["extra_body"] == {"thinking": {"type": "enabled"}} and p["reasoning_effort"] == "high"
    system = p["messages"][0]["content"]
    assert "JSON" in system and json.dumps(planner.SCHEMA) in system   # JSON mode needs both


def test_empty_reply_is_retried_and_both_attempts_are_billed():
    tracer = Tracer()
    out = call(planner, "planner", FakeDeepSeekClient(queued={"Planner": [""]}), tracer=tracer)
    assert out == PLAN_OUT
    span = tracer.spans[-1]
    assert (span["attempts"], span["prompt_tokens"]) == (2, 2000)


def test_off_schema_twice_raises():
    bad = json.dumps({"thesis": 5, "conditions": [], "facts_cited": []})
    with pytest.raises(LLMError, match="should be string"):
        call(planner, "planner", FakeDeepSeekClient(queued={"Planner": [bad, bad]}))


def test_invalid_json_then_valid_succeeds():
    out = call(naysayer, "naysayer", FakeDeepSeekClient(queued={"Naysayer": ["{not json"]}))
    assert out["verdict"] == "approve"


def test_truncated_reply_raises_without_retry():
    client = FakeDeepSeekClient(finish_reason="length")
    with pytest.raises(LLMError, match="length"):
        call(planner, "planner", client)
    assert len(client.requests) == 1


@pytest.mark.parametrize("out, reason", [
    ([], "not a JSON object"),
    ({"conditions": [], "facts_cited": []}, "missing key 'thesis'"),
    (dict(PLAN_OUT, conditions="ret_5d > 0"), "should be array"),
    (dict(PLAN_OUT, facts_cited="ret_5d"), "should be array"),
])
def test_schema_error(out, reason):
    assert reason in schema_error(out, planner.SCHEMA)


@pytest.mark.parametrize("value, ok", [(97, True), (97.5, True), (True, False), ("97", False)])
def test_schema_error_number_type(value, ok):
    schema = {"required": ["x"], "properties": {"x": {"type": "number"}}}
    assert (schema_error({"x": value}, schema) is None) == ok


def test_claude_sonnet_uses_server_side_fallback_and_haiku_does_not():
    client = FakeClient()
    call(researcher, "researcher", client, provider="claude")
    call(planner, "planner", client, provider="claude")
    haiku, sonnet = client.requests
    assert (haiku["model"], sonnet["model"]) == ("claude-haiku-5-5", "claude-sonnet-5-5")
    assert sonnet["fallbacks"] == "default" and "fallbacks" not in haiku
    assert all(r["output_config"]["format"]["type"] == "json_schema" for r in client.requests)


def test_unknown_provider():
    with pytest.raises(ValueError):
        make_llm(Tracer(), "nope", object())


def test_reporter_role_exists():
    from src.llm import DEEPSEEK_THINKING, MODELS
    assert MODELS["deepseek"]["reporter"] == "deepseek-flash" and MODELS["claude"]["reporter"] == "claude-haiku-5-5"
    assert DEEPSEEK_THINKING["reporter"] is False
