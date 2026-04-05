# Standard library
import json
import re
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def extract_json_array(text: str) -> list[str]:
    candidate = text.strip()
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", candidate, re.DOTALL)
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        return []

    return []


def chunks_to_context(chunks: list[dict[str, Any]], limit: int) -> str:
    lines: list[str] = []
    for i, chunk in enumerate(chunks[:limit], start=1):
        text = chunk.get("text", "")
        lines.append(f"[{i}] {text}")
    return "\n".join(lines)
