"""OpenCode CLI LLM client - runs opencode CLI as subprocess.

Self-contained: reads config from environment variables, no backend imports.
"""

import asyncio
import os
import json
import shutil
import time
from typing import Any, Dict, List, Optional

from .base import LLMClient, LLMResponse, ProviderHealth


def _get_settings():
    """Get OpenCode CLI settings from environment variables with defaults.

    Self-contained: no imports from web layer.
    """
    def _str(name: str, default: str = "") -> str:
        return os.environ.get(name, default)

    def _str_list(name: str, default: Optional[List[str]] = None) -> List[str]:
        """
        A comma-separated environment variable, as a list.

        The default is a list, not a string: reading the variable as a string
        and splitting it afterwards would try to split the default itself,
        and a list has no ``split``.
        """
        val = os.environ.get(name)
        if val is None:
            return list(default or [])
        return [m.strip() for m in val.split(",") if m.strip()]

    def _int(name: str, default: int = 30) -> int:
        try:
            return int(os.environ.get(name, default))
        except (ValueError, TypeError):
            return default

    def _bool(name: str, default: bool = "cli") -> str:
        return os.environ.get(name, default)

    return type("OpenCodeSettings", (), {
        "opencode_models": _str_list("OPENCODE_MODELS", []),
        "OPENCODE_TIMEOUT_S": _int("OPENCODE_TIMEOUT_S", 30),
        "OPENCODE_MODE": _str("OPENCODE_MODE", "cli"),
    })()


def _opencode_executable() -> str:
    """Resolve the opencode binary.

    npm installs expose ``opencode`` as a ``.cmd``/``.ps1`` wrapper with no
    ``opencode.exe``, and ``asyncio.create_subprocess_exec`` searches the
    PATH for the bare name with an implied ``.exe`` extension only - so the
    full wrapper path is resolved here. Falls back to the bare name, which
    works on installs that do ship a real executable.
    """
    return shutil.which("opencode") or "opencode"


class OpenCodeCLIClient(LLMClient):
    """OpenCode CLI client for free models via subprocess.

    Self-contained: all configuration from environment variables.
    """

    def __init__(self):
        settings = _get_settings()
        self._models = settings.opencode_models
        self._timeout = settings.OPENCODE_TIMEOUT_S
        self._mode = settings.OPENCODE_MODE  # "cli" or "serve"
        self._current_model_idx = 0
        self._last_rate_limit_remaining: int | None = None
        self._last_rate_limit_total: int | None = None

    @property
    def name(self) -> str:
        return "opencode_cli"

    @property
    def default_model(self) -> str:
        return self._models[0] if self._models else ""

    def _get_current_model(self) -> str:
        """Get current model, rotating through available models."""
        if not self._models:
            return ""
        return self._models[self._current_model_idx % len(self._models)]

    def _rotate_model(self):
        """Rotate to next model on failure."""
        self._current_model_idx += 1

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Run opencode CLI as subprocess."""
        start = time.monotonic()
        model = self._get_current_model()

        # Build prompt from messages
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        if self._mode == "cli":
            response_text = await self._run_cli(prompt, model)
        else:
            response_text = await self._run_serve(prompt, model)

        if response_text is None or not str(response_text).strip():
            # Empty output must fail over instead of being cached as success.
            raise ValueError(f"opencode_cli returned empty content (model={model})")

        latency_ms = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            text=response_text,
            model=model,
            provider=self.name,
            input_tokens=len(prompt.split()),
            output_tokens=len(response_text.split()),
            latency_ms=latency_ms,
        )

    async def _run_cli(self, prompt: str, model: str) -> str:
        """Run opencode CLI in non-interactive mode.

        The prompt is piped via stdin rather than argv: Windows command
        lines cap at 32767 chars, which full-page extraction prompts exceed.
        """
        cmd = [_opencode_executable(), "run", "-m", f"opencode/{model}"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(prompt.encode("utf-8")),
                timeout=self._timeout,
            )

            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                if "429" in error_msg or "FreeUsageLimitError" in error_msg:
                    self._rotate_model()
                    raise Exception(f"Rate limited: {error_msg}")
                raise Exception(f"OpenCode CLI error: {error_msg}")

            return stdout.decode().strip()

        except asyncio.TimeoutError:
            raise Exception(f"OpenCode CLI timeout after {self._timeout}s")

    async def _run_serve(self, prompt: str, model: str) -> str:
        """Call local opencode serve instance."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:4096/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def list_models(self) -> List[str]:
        """Return configured models."""
        return self._models

    async def health_check(self) -> ProviderHealth:
        """Check OpenCode CLI health."""
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                _opencode_executable(), "run", "-m", f"opencode/{self._get_current_model()}",
                "hi",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=30,
            )

            latency_ms = int((time.monotonic() - start) * 1000)

            if proc.returncode == 0:
                return ProviderHealth(
                    provider=self.name,
                    model=self._get_current_model(),
                    status="healthy",
                    latency_ms=latency_ms,
                )
            else:
                return ProviderHealth(
                    provider=self.name,
                    model=self._get_current_model(),
                    status="degraded",
                    latency_ms=latency_ms,
                    error=stderr.decode().strip(),
                )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                model=self._get_current_model(),
                status="unavailable",
                latency_ms=int((time.monotonic() - start) * 1000),
                error=str(e),
            )

    async def close(self):
        """Close any open resources."""
        pass