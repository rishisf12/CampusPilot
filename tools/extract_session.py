"""Extract frontend file contents from the attached session JSON."""
import json
import sys
from pathlib import Path

SESSION = Path.home() / "Downloads" / "multiple-sessions-for-faster-project-completion.json"
OUT = Path(__file__).resolve().parent / "session_extract"
OUT.mkdir(exist_ok=True)

data = json.loads(SESSION.read_text(encoding="utf-8"))
print("top-level keys:", list(data.keys()))

messages = data.get("messages") or []
print("messages:", len(messages))


def walk(obj, path=()):
    """Yield (path, dict) for every dict in the structure."""
    if isinstance(obj, dict):
        yield path, obj
        for key, value in obj.items():
            yield from walk(value, path + (key,))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from walk(item, path + (index,))


# Find every write/edit tool call and record the file path + payload.
edits = {}
for path, node in walk(messages):
    state = node.get("state")
    if not isinstance(state, dict):
        continue
    args = state.get("input") or state.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (ValueError, TypeError):
            continue
    if not isinstance(args, dict):
        continue
    file_path = args.get("filePath") or args.get("path")
    if not file_path or not isinstance(file_path, str):
        continue
    content = args.get("content")
    if not isinstance(content, str):
        continue
    edits.setdefault(file_path, []).append({"content": content})

print(f"\nfiles touched: {len(edits)}")
for path in sorted(edits):
    versions = edits[path]
    has_content = sum(1 for v in versions if v.get("content"))
    print(f"  {path}  ({len(versions)} call(s), {has_content} with content)")

# Persist the latest full content per file.
for path, versions in edits.items():
    contents = [v for v in versions if v.get("content")]
    if not contents:
        continue
    target = OUT / Path(path).name
    target.write_text(contents[-1]["content"], encoding="utf-8")
    print(f"wrote {target} ({len(contents[-1]['content'])} chars)")