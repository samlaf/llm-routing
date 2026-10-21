"""Claude models called through the Claude Code CLI.

The CLI runs on the user's Claude login, so no API key is needed. Its own system
prompt, tools and settings are switched off, but it still adds a fixed preamble
to every request. `overhead_tokens` measures that preamble so recorded costs
count only our prompt.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass

MODELS = {
    "small": "claude-haiku-5-5",
    "medium": "claude-sonnet-5-5",
    "frontier": "claude-opus-5-5",
}
# List price in dollars per token: (input, output). Thinking is billed as output.
PRICES = {
    "small": (0.10e-6, 0.50e-6),
    "medium": (2.00e-6, 10.00e-6),
    "frontier": (4.00e-6, 20.00e-6),
}
# Haiku and Opus default to medium effort and Sonnet to high. One fixed level
# keeps the models apart by size alone.
EFFORT = "medium"
CALL_TIMEOUT_S = 600
# A hard budget needs a worst case per call. Haiku occasionally thinks for
# 6–9k tokens, and capping it at 8192 would make its worst case for every task
# cost more than the whole budget.
MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True)
class Reply:
    text: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int


def ask(model: str, prompt: str, system: str) -> Reply:
    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--model",
            MODELS[model],
            "--effort",
            EFFORT,
            "--system-prompt",
            system,
            "--tools",
            "",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--no-session-persistence",
            "--max-turns",
            "1",
            "--output-format",
            "json",
        ],
        # A neutral directory, so no project files leak into the request.
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        timeout=CALL_TIMEOUT_S,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude CLI failed: {result.stderr or result.stdout}")
    if data.get("is_error"):
        raise RuntimeError(f"claude CLI error: {data.get('result')}")
    usage = data["usage"]
    return Reply(
        text=data["result"],
        input_tokens=usage["input_tokens"]
        + usage["cache_creation_input_tokens"]
        + usage["cache_read_input_tokens"],
        output_tokens=usage["output_tokens"],
        thinking_tokens=usage.get("output_tokens_details", {}).get(
            "thinking_tokens", 0
        ),
    )


def overhead_tokens(model: str) -> int:
    """Input tokens the CLI adds to every request, from a near-empty one."""
    return ask(model, ".", system=".").input_tokens


def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES[model]
    return price_in * input_tokens + price_out * output_tokens
