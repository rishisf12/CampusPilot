"""JSON repair utilities - handle malformed LLM output."""

import json
import re
from typing import Any, Optional


def strip_thinking_blocks(text: str) -> str:
    """Strip reasoning blocks from LLM output.

    Handles  blocks and variants.
    Only removes content within thinking markers, preserves surrounding text.
    """
    if not text:
        return ""

    # Remove  blocks and variants
    text = re.sub(r"<(?i:thinking|thought>).*?</(?:thinking|thought>)>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove standalone thinking markers without content
    text = re.sub(r"<think\s*/?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</think\s*>?", "", text, flags=re.IGNORECASE)

    # Clean up isolated periods/whitespace left after stripping
    text = re.sub(r"^\.?\s*$", "", text)  # Remove isolated period or whitespace-only text
    text = text.strip()

    return text


def extract_json(text: str) -> Optional[str]:
    """Extract first valid JSON object or array from text."""
    text = text.strip()

    # Try direct parse first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Try to find JSON object or array
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        # Find matching end
        depth = 0
        in_string = False
        escape = False
        for i, ch in enumerate(text[start_idx:], start_idx):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start_idx:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break
    return None


def repair_json(text: str) -> Optional[str]:
    """Attempt to repair common JSON issues.

    Returns repaired JSON string or None if unrepairable.
    """
    text = text.strip()

    # Remove markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)

    # Remove trailing commas
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Fix single quotes to double quotes (carefully)
    # Only if the text looks like JSON
    if text.startswith("{") or text.startswith("["):
        # Replace single-quoted strings
        text = re.sub(r"'([^']*)'", r'"\1"', text)

    # Fix unquoted keys
    text = re.sub(r"(\w+):", r'"\1":', text)

    # Try to parse
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from text
    extracted = extract_json(text)
    if extracted:
        return extracted

    return None


def parse_llm_json(text: str) -> Optional[Any]:
    """Parse JSON from LLM output with full repair pipeline.

    Returns parsed object or None if unrepairable.
    """
    # Step 1: Strip thinking blocks
    text = strip_thinking_blocks(text)

    # Step 2: Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Step 3: Extract JSON from text
    extracted = extract_json(text)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    # Step 4: Try repair
    repaired = repair_json(text)
    if repaired:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    return None


def validate_with_pydantic(model_class, data: dict) -> Optional[Any]:
    """Validate parsed JSON with a Pydantic model."""
    try:
        return model_class(**data)
    except Exception:
        return None