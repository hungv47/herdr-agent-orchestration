"""Retrieve original content represented by a Headroom CCR marker."""

from __future__ import annotations

import httpx
from tools.registry import tool_error, tool_result

_PROXY_URL = "http://127.0.0.1:8787"

HEADROOM_RETRIEVE_SCHEMA = {
    "name": "headroom_retrieve",
    "description": "Retrieve full content for a Headroom compression hash. Do not retry this tool.",
    "parameters": {
        "type": "object",
        "properties": {"hash": {"type": "string", "description": "CCR marker hash"}},
        "required": ["hash"],
    },
}


def _handle_headroom_retrieve(args: dict, **kw) -> str:
    hash_key = str(args.get("hash") or "").strip().strip("<>")
    hash_key = hash_key.removeprefix("ccr:").removeprefix("hash=").split(",")[0].strip()
    if not hash_key:
        return tool_error("hash is required")
    try:
        response = httpx.post(f"{_PROXY_URL}/v1/retrieve", json={"hash": hash_key}, timeout=15)
    except httpx.HTTPError as error:
        return tool_error(f"Headroom is unreachable ({type(error).__name__}); rerun the original command once.")
    if response.status_code == 404:
        return tool_error("Content expired; rerun the original command once.")
    if response.status_code != 200:
        return tool_error(f"Headroom returned HTTP {response.status_code}.")
    data = response.json()
    return tool_result({
        "original_content": data.get("original_content", ""),
        "original_tokens": data.get("original_tokens"),
        "tool_name": data.get("tool_name"),
    })


def register(ctx) -> None:
    ctx.register_tool(
        name="headroom_retrieve",
        toolset="headroom",
        schema=HEADROOM_RETRIEVE_SCHEMA,
        handler=_handle_headroom_retrieve,
        emoji="🗜️",
    )
