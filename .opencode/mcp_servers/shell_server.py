#!/usr/bin/env python3
"""
Shell MCP Server - Execute shell commands via MCP protocol.

Design notes
------------
Output is captured through temporary files rather than pipes. On Windows,
``shell=True`` means the direct child is ``cmd.exe``, and killing it does not
kill the grandchild it spawned; the grandchild keeps the write end of the pipe
open, so a subsequent ``communicate()`` waits for an EOF that never arrives and
the whole MCP server blocks forever. Temp files have no such problem: the
reader polls the file, and a stuck grandchild cannot hold it open.

Long-running commands (servers) are started detached and return immediately.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Optional


def send_message(message: Dict[str, Any]) -> None:
    """Send a JSON-RPC message to stdout."""
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def receive_message() -> Optional[Dict[str, Any]]:
    """Read a JSON-RPC message from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "shell-mcp-server", "version": "3.0.0"},
    }


def handle_list_tools(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle list tools request."""
    return {
        "tools": [
            {
                "name": "shell_command",
                "description": (
                    "Execute a shell command. For long-running processes (servers), "
                    "use background=true: it starts the process detached and returns "
                    "immediately instead of waiting for it to exit."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory for the command",
                        },
                        "timeout": {
                            "type": "number",
                            "description": "Timeout in seconds for foreground commands",
                            "default": 30,
                        },
                        "background": {
                            "type": "boolean",
                            "description": (
                                "If true, start the process detached in the background "
                                "and return immediately"
                            ),
                            "default": False,
                        },
                    },
                    "required": ["command"],
                },
            }
        ]
    }


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _run_background(command: str, cwd: Optional[str]) -> Dict[str, Any]:
    """Start a detached process and return immediately."""
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
        start_new_session=True if sys.platform != "win32" else False,
    )
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Started background process (PID: {proc.pid})\n"
                    f"Command: {command}\n"
                    f"Working directory: {cwd or os.getcwd()}"
                ),
            }
        ],
        "isError": False,
    }


def _run_foreground(command: str, cwd: Optional[str], timeout: int) -> Dict[str, Any]:
    """Run a command to completion, capturing output through temp files."""
    out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".out")
    err_file = tempfile.NamedTemporaryFile(delete=False, suffix=".err")
    out_path, err_path = out_file.name, err_file.name
    out_file.close()
    err_file.close()

    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=open(out_path, "wb"),
            stderr=open(err_path, "wb"),
            creationflags=creation_flags,
            start_new_session=True if sys.platform != "win32" else False,
        )
    except Exception as exc:
        _cleanup(out_path, err_path)
        return _error(str(exc))

    timed_out = False
    deadline = time.time() + max(1, timeout)
    while True:
        if proc.poll() is not None:
            break
        if time.time() > deadline:
            timed_out = True
            _terminate_tree(proc)
            break
        time.sleep(0.1)

    stdout = _read_file(out_path)
    stderr = _read_file(err_path)
    _cleanup(out_path, err_path)

    if timed_out:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Command timed out after {timeout} seconds "
                        f"(process tree terminated).\n\n"
                        f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                    ),
                }
            ],
            "isError": True,
        }

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Exit code: {proc.returncode}\n\n"
                    f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                ),
            }
        ],
        "isError": proc.returncode != 0,
    }


def _terminate_tree(proc) -> None:
    """Kill the process and anything it spawned.

    On Windows the direct child is cmd.exe; the real command is a grandchild
    that survives the parent. taskkill /T kills the whole tree.
    """
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=15,
            )
        else:
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _cleanup(*paths: str) -> None:
    for path in paths:
        try:
            os.unlink(path)
        except OSError:
            pass


def _error(message: str) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": f"Error: {message}"}],
        "isError": True,
    }


def handle_call_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle call tool request."""
    name = params.get("name", "")
    arguments = params.get("arguments", {})

    if name != "shell_command":
        return _error(f"Unknown tool: {name}")

    command = arguments.get("command", "")
    cwd = arguments.get("cwd", None)
    timeout = arguments.get("timeout", 30)
    background = arguments.get("background", False)

    if not command:
        return _error("command is required")

    try:
        if background:
            return _run_background(command, cwd)
        return _run_foreground(command, cwd, int(timeout))
    except Exception as exc:
        return _error(str(exc))


def main() -> None:
    """Main entry point for the shell MCP server."""
    while True:
        message = receive_message()
        if message is None:
            break

        method = message.get("method", "")
        params = message.get("params", {})
        msg_id = message.get("id")

        if method == "initialize":
            result = handle_initialize(params)
        elif method == "initialized":
            continue
        elif method == "tools/list":
            result = handle_list_tools(params)
        elif method == "tools/call":
            result = handle_call_tool(params)
        else:
            result = {
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }

        response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
        send_message(response)


if __name__ == "__main__":
    main()
