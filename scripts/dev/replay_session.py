"""
Reconstruct the final state of every file from the session JSON.

The session records two kinds of tool call:
  * ``write`` - the full new file content
  * ``edit``  - an oldString -> newString patch

Replaying them in the order they appear (write resets the buffer, edit patches
it) recovers the file as it stood at the end of that session.
"""
import json
from collections import defaultdict
from pathlib import Path

SESSION = Path.home() / "Downloads" / "multiple-sessions-for-faster-project-completion.json"
ROOT = Path(r"C:\Users\Appex\Documents\Default Project\CampusPilot")
OUT = ROOT / "tools" / "session_extract"

data = json.loads(SESSION.read_text(encoding="utf-8"))
messages = data.get("messages") or []

# Collect (index, kind, args) for every write/edit call, in message order.
calls = defaultdict(list)


def consider(index, node):
    if not isinstance(node, dict):
        return
    tool = node.get("tool") or node.get("name") or ""
    state = node.get("state")
    if not isinstance(state, dict):
        return
    args = state.get("input") or state.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (ValueError, TypeError):
            return
    if not isinstance(args, dict):
        return
    path = args.get("filePath") or args.get("path")
    if not isinstance(path, str):
        return
    if tool == "write" and isinstance(args.get("content"), str):
        calls[path].append((index, "write", args["content"]))
    elif tool == "edit":
        old, new = args.get("oldString"), args.get("newString")
        if isinstance(old, str) and isinstance(new, str):
            calls[path].append((index, "edit", (old, new)))
    elif tool in ("multiedit", "multi_edit"):
        edits = args.get("edits")
        if isinstance(edits, list):
            for item in edits:
                if isinstance(item, dict):
                    old, new = item.get("oldString"), item.get("newString")
                    if isinstance(old, str) and isinstance(new, str):
                        calls[path].append((index, "edit", (old, new)))


def walk(index, obj):
    if isinstance(obj, dict):
        consider(index, obj)
        for value in obj.values():
            walk(index, value)
    elif isinstance(obj, list):
        for item in obj:
            walk(index, item)


for position, message in enumerate(messages):
    walk(position, message)


def apply_edit(content: str, old: str, new: str) -> str:
    """Apply one patch, tolerating CRLF/LF differences."""
    if old in content:
        return content.replace(old, new, 1)
    if old.replace("\r\n", "\n") in content.replace("\r\n", "\n"):
        normalised = content.replace("\r\n", "\n")
        return normalised.replace(old.replace("\r\n", "\n"), new.replace("\r\n", "\n"), 1)
    return content  # patch target not present; leave the buffer untouched


frontend = {}
for path, operations in calls.items():
    normalised = path.replace("\\", "/")
    if "/frontend/" not in normalised:
        continue
    operations.sort(key=lambda item: item[0])
    buffer = None
    applied = 0
    for _, kind, payload in operations:
        if kind == "write":
            buffer = payload
            applied += 1
        elif buffer is not None:
            updated = apply_edit(buffer, payload[0], payload[1])
            if updated is not buffer:
                buffer = updated
                applied += 1
    if buffer:
        relative = normalised.split("/frontend/", 1)[1].lstrip("/")
        frontend[relative] = buffer

print(f"reconstructed {len(frontend)} frontend files\n")
for relative in sorted(frontend):
    print(f"  {relative:<48} {len(frontend[relative]):>7} chars")

OUT.mkdir(parents=True, exist_ok=True)
for relative, content in frontend.items():
    target = OUT / "frontend" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
print(f"\nwritten to {OUT / 'frontend'}")