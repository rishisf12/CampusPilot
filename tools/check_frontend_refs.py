"""Find references to identifiers that are never defined or imported.

`npm run build` cannot catch these: esbuild treats an unknown name as a global
and lets it through, so a typo like `writePendingEmail` (a function that never
existed) ships cleanly and only throws when a student clicks the button. That
happened here once already - signup silently did nothing because the handler
threw before it could change screens.

This walks each source file, collects the names it calls, and reports any that
are not declared, imported, or known globals. Crude, but it catches exactly the
class of bug a bundler waves through.

Usage:  python tools/check_frontend_refs.py [directory]
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "frontend" / "src"

#: Names that are legitimately global in a browser/React module.
KNOWN_GLOBALS = {
    # browser
    "window", "document", "navigator", "localStorage", "sessionStorage",
    "console", "fetch", "setTimeout", "clearTimeout", "setInterval",
    "clearInterval", "requestAnimationFrame", "cancelAnimationFrame",
    "location", "history", "alert", "confirm", "prompt", "URL", "URLSearchParams",
    "AbortController", "Blob", "File", "FileReader", "FormData", "Headers",
    "atob", "btoa", "TextDecoder", "TextEncoder", "crypto", "EventSource",
    "Date", "Math", "JSON", "Object", "Array", "String", "Number", "Boolean",
    "Promise", "RegExp", "Error", "TypeError", "RangeError", "SyntaxError",
    "Map", "Set", "WeakMap", "WeakSet", "Symbol", "BigInt", "Proxy", "Reflect",
    "Intl", "parseInt", "parseFloat", "isNaN", "isFinite", "encodeURIComponent",
    "decodeURIComponent", "encodeURI", "decodeURI", "undefined", "NaN",
    "Infinity", "globalThis", "queueMicrotask", "structuredClone",
    "Uint8Array", "Int16Array", "Int32Array", "Float32Array", "Float64Array",
    "ArrayBuffer", "DataView", "CustomEvent", "performance", "crypto",
    # react
    "useState", "useEffect", "useCallback", "useMemo", "useRef", "useContext",
    "useReducer", "createContext", "memo", "forwardRef", "Fragment",
    "StrictMode", "React",
}

#: Keywords that the call regex cannot tell apart from a function call.
KEYWORDS = {
    "catch", "finally", "async", "await", "function", "return", "if", "else",
    "for", "while", "switch", "case", "do", "new", "typeof", "instanceof",
    "delete", "void", "in", "of", "try", "throw", "class", "extends", "super",
    "this", "import", "export", "default", "with", "yield", "debugger",
}

#: A call: an identifier immediately followed by "(" and not preceded by a dot,
#: so member calls like `api.get(...)` and definitions are excluded.
CALL_RE = re.compile(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(")

IMPORT_RE = re.compile(
    r"import\s+(?:[\w*\s{},$]+\s+from\s+)?['\"][^'\"]+['\"]", re.IGNORECASE
)
NAMED_IMPORT_RE = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*(?:,|as\s)", re.MULTILINE)
DEFAULT_IMPORT_RE = re.compile(r"import\s+([A-Za-z_$][\w$]*)\s*(?:,|from)", re.MULTILINE)
DESTRUCTURED_RE = re.compile(r"^\s*\{([^}]*)\}\s*=", re.MULTILINE | re.DOTALL)
DECL_RE = re.compile(
    r"\b(?:function|class)\s+([A-Za-z_$][\w$]*)"
    r"|\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
    r"|([A-Za-z_$][\w$]*)\s*(?:=|\(|=>)"
)


def strip_comments_and_strings(text: str) -> str:
    """
    Blank out comments and the inside of string/template literals.

    Both are replaced with spaces rather than removed, so line numbers - and the
    offsets used to report them - stay correct.
    """
    out = []
    index = 0
    length = len(text)
    # Tracks a template literal's ${...} nesting so real code inside one is kept.
    brace_depth = 0

    while index < length:
        char = text[index]
        nxt = text[index + 1] if index + 1 < length else ""

        # Line comment.
        if char == "/" and nxt == "/":
            while index < length and text[index] != "\n":
                out.append(" ")
                index += 1
            continue

        # Block comment.
        if char == "/" and nxt == "*":
            while index < length and not (text[index] == "*" and index + 1 < length and text[index + 1] == "/"):
                out.append("\n" if text[index] == "\n" else " ")
                index += 1
            out.append("  ")
            index += 2
            continue

        # String or template literal.
        if char in "'\"`":
            quote = char
            out.append(" ")
            index += 1
            while index < length:
                current = text[index]
                if current == "\\":
                    out.append("  ")
                    index += 2
                    continue
                if current == "\n":
                    out.append("\n")
                    index += 1
                    continue
                if quote == "`" and current == "$" and index + 1 < length and text[index + 1] == "{":
                    # Keep the expression: it is real code.
                    out.append("${")
                    index += 2
                    depth = 1
                    while index < length and depth:
                        if text[index] == "{":
                            depth += 1
                        elif text[index] == "}":
                            depth -= 1
                        out.append(text[index])
                        index += 1
                    continue
                if current == quote:
                    out.append(" ")
                    index += 1
                    break
                out.append(" ")
                index += 1
            continue

        out.append(char)
        index += 1

    del brace_depth
    return "".join(out)


def declared_names(text: str) -> set[str]:
    """Every name the file defines or brings into scope."""
    names: set[str] = set()

    for match in re.finditer(
        r"import\s+(?:([\w$]+)\s*,\s*)?(?:\{([^}]*)\})?\s*(?:([\w$]+)\s*)?from",
        text,
    ):
        default_a, braces, default_b = match.groups()
        for name in (default_a, default_b):
            if name:
                names.add(name)
        if braces:
            for part in braces.split(","):
                part = part.strip()
                if not part:
                    continue
                # "a as b" - the local binding is the alias.
                names.add(part.split(" as ")[-1].strip())
        # "import './side-effect'"
    for match in re.finditer(r"import\s+['\"]", text):
        del match

    for match in re.finditer(
        r"\b(?:export\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", text
    ):
        names.add(match.group(1))
    for match in re.finditer(r"\b(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", text):
        names.add(match.group(1))

    # const/let/var, including destructured patterns.
    for match in re.finditer(
        r"\b(?:const|let|var)\s+(\{[^}]*\}|\[[^\]]*\]|[A-Za-z_$][\w$]*)", text
    ):
        token = match.group(1)
        if token[0] in "{[":
            for part in re.findall(r"[A-Za-z_$][\w$]*", token):
                names.add(part)
        else:
            names.add(token)

    # Function parameters and destructured assignments inside function bodies.
    for match in re.finditer(r"\(([^)]*)\)\s*(?:=>|\{)", text, re.DOTALL):
        for part in re.findall(r"[A-Za-z_$][\w$]*", match.group(1)):
            names.add(part)
    for match in re.finditer(r"\(([^)]*)\)\s*(?:async\s*)?\w*\s*(?:=>|\{)", text):
        for part in re.findall(r"[A-Za-z_$][\w$]*", match.group(1)):
            names.add(part)

    # Class members.
    for match in re.finditer(r"^\s*(?:static\s+)?([A-Za-z_$][\w$]*)\s*\(", text, re.MULTILINE):
        names.add(match.group(1))

    return names


def main() -> int:
    if not SRC.is_dir():
        print(f"no source directory at {SRC}")
        return 1

    files = sorted(
        p for p in SRC.rglob("*") if p.suffix in (".js", ".jsx") and "node_modules" not in p.parts
    )
    if not files:
        print(f"no .js/.jsx files under {SRC}")
        return 1

    problems = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")

        # Strip comments and string bodies: prose like "the student's weekday (IST)"
        # and prose inside a JSX label are not calls, and flagging them buries
        # the real findings.
        live = strip_comments_and_strings(text)

        names = declared_names(live)
        for match in CALL_RE.finditer(live):
            called = match.group(1)
            if called in names or called in KNOWN_GLOBALS or called in KEYWORDS:
                continue
            # JSX components are capitalised and called as <Foo />, not Foo().
            line_no = live[: match.start()].count("\n") + 1
            problems.append((path.relative_to(SRC.parent), line_no, called))

    print(f"scanned {len(files)} files under {SRC}\n")
    if not problems:
        print("no undefined references found")
        return 0

    print(f"{len(problems)} suspicious call(s):\n")
    for path, line_no, called in problems:
        print(f"  {path}:{line_no}  {called}()")
    print("\nEach of these is a ReferenceError waiting for a click.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
