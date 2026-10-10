"""Researcher: turns a setup's price features into short facts, each citing its source key."""
import json

from src.agents import DATA_NOTE, FEATURE_GUIDE
from src.features import FEATURE_NAMES

KEYS = list(FEATURE_NAMES) + ["recent_closes"]

SYSTEM = (
    "You are the Researcher on a paper-trading research team. Given price features for one "
    "setup day, write 3 to 6 short factual statements a trader would care about (trend, "
    "momentum, volatility, distance from averages). Each fact cites exactly one source key and "
    "states its value. State facts only, no recommendation. " + FEATURE_GUIDE + " " + DATA_NOTE
)

SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": {"type": "string", "enum": KEYS},
                               "statement": {"type": "string"}},
                "required": ["key", "statement"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["facts"],
    "additionalProperties": False,
}


def run(llm, features, recent_closes, **tags):
    """-> {source_key: statement}. Raises if no fact has a valid key."""
    prompt = json.dumps({"features": features, "recent_closes": recent_closes})
    out = llm("researcher", SYSTEM, prompt, SCHEMA, **tags)
    facts = {f["key"]: f["statement"] for f in out.get("facts", []) if f.get("key") in KEYS}
    if not facts:
        raise ValueError("researcher returned no facts with a valid key")
    return facts
