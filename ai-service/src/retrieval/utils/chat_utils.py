# Standard library
from typing import Any


def normalize_chat_history(chat_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_map = {
        "USER": "user",
        "AI": "assistant",
        "SYSTEM": "system",
        "user": "user",
        "assistant": "assistant",
        "system": "system",
    }

    normalized: list[dict[str, Any]] = []
    for item in chat_history:
        role = role_map.get(str(item.get("role", "")).strip(), "user")
        normalized.append({
            "role": role,
            "content": str(item.get("content", "")),
        })
    return normalized
