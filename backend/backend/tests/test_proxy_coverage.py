"""The dev-server proxy list must cover every router the backend mounts.

This exists because that list drifted once already. ``/monitoring`` and
``/collect`` were added to the backend and to ``nginx.conf``, but not to
``vite.config.js``, so the monitoring requests worked in the Docker container
and 404'd under ``npm run dev``.

That is the worst shape of bug: it breaks only in the environment nobody
deploys, so it is found by a user rather than by CI, and the natural reaction
is to "fix" the backend rather than the list.

Three separate copies of this list used to exist (the FastAPI routers, the Vite
config, and nginx). ``nginx.conf`` no longer keeps one - it uses
``try_files ... @backend`` and needs no per-router entry. This module reduces it
to two and asserts they agree.

Also checks the reverse direction: a prefix listed for proxying that the backend
does not serve is dead config, and it hides the fact that the real router is
missing.
"""
from __future__ import annotations

import re
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
VITE_CONFIG = REPO / "frontend" / "vite.config.js"
NGINX_CONF = REPO / "frontend" / "nginx.conf"
MAIN = BACKEND / "main.py"

#: `APIRouter(prefix="/collect", ...)` and friends.
_ROUTER_PREFIX_RE = re.compile(r'APIRouter\(\s*prefix=["\']([^"\']+)["\']')
#: `app.include_router(monitoring.collect_router)` with no prefix argument.
_BARE_INCLUDE_RE = re.compile(r'include_router\(\s*([\w.]+)\s*\)')
#: `app.include_router(x.router, prefix="/auth", tags=[...])`
_PREFIXED_INCLUDE_RE = re.compile(
    r'include_router\(\s*[\w.]+\s*,\s*prefix=["\']([^"\']+)["\']'
)
#: Quoted entries in the `proxied` array in vite.config.js.
_VITE_ENTRY_RE = re.compile(r"'(/[\w/-]*)'")
#: Bare routes declared straight on the app, e.g. `@app.get("/metrics")`. These
#: belong to no router, so the router regexes above cannot see them - and
#: forgetting them is exactly the drift this module exists to catch.
_APP_ROUTE_RE = re.compile(r'@app\.(?:get|post|put|delete|patch)\(\s*["\'](/[^"\']*)["\']')


def _backend_router_names() -> set[str]:
    """Module paths passed to a bare `include_router(...)`, e.g. `teams.router`."""
    text = MAIN.read_text(encoding="utf-8")
    return set(_BARE_INCLUDE_RE.findall(text))
    # These two are defined as attributes rather than module-level names, so they
    # cannot be resolved from main.py alone. They are listed here explicitly.


def _backend_prefixes() -> set[str]:
    """Every top-level path prefix the backend serves."""
    prefixes: set[str] = set()

    for path in BACKEND.rglob("*.py"):
        if "venv" in path.parts or "tests" in path.parts:
            continue
        prefixes.update(_ROUTER_PREFIX_RE.findall(path.read_text(encoding="utf-8")))

    prefixes.update(_PREFIXED_INCLUDE_RE.findall(MAIN.read_text(encoding="utf-8")))
    prefixes.update(_APP_ROUTE_RE.findall(MAIN.read_text(encoding="utf-8")))

    # main.py mounts these two without a prefix argument; resolve their own
    # declared prefix instead of hardcoding a guess.
    for name in _backend_router_names():
        for path in BACKEND.rglob(f"{name.split('.')[-1]}.py"):
            if "venv" in path.parts:
                continue
            found = _ROUTER_PREFIX_RE.findall(path.read_text(encoding="utf-8"))
            prefixes.update(found)

    return {p if p.startswith("/") else f"/{p}" for p in prefixes if p.strip("/")}


def _vite_prefixes() -> set[str]:
    text = VITE_CONFIG.read_text(encoding="utf-8")
    start = text.index("const proxied")
    end = text.index("]", start)
    return set(_VITE_ENTRY_RE.findall(text[start:end]))


class TestProxyCoverage:
    def test_vite_config_exists(self):
        assert VITE_CONFIG.is_file(), f"missing {VITE_CONFIG}"
        assert NGINX_CONF.is_file(), f"missing {NGINX_CONF}"

    def test_backend_prefixes_are_discoverable(self):
        """Guards the discovery itself.

        If a regex stops matching after a FastAPI refactor, this list silently
        becomes empty and every other test in the class passes vacuously - which
        is the failure mode of a test that only asserts absence.
        """
        prefixes = _backend_prefixes()
        assert "/auth" in prefixes, f"failed to discover backend routers: {prefixes}"
        assert "/feedback" in prefixes
        assert len(prefixes) >= 10, f"suspiciously few prefixes discovered: {prefixes}"

    def test_every_backend_prefix_is_proxied_by_vite(self):
        missing = sorted(_backend_prefixes() - _vite_prefixes())
        assert not missing, (
            f"vite.config.js does not proxy {missing}. Under `npm run dev` these "
            "endpoints 404 from the SPA origin, which looks like a missing "
            "endpoint rather than a missing proxy rule."
        )

    def test_vite_does_not_proxy_a_prefix_the_backend_lacks(self):
        """Dead config hides the real bug.

        A prefix listed here that the backend does not serve means someone
        renamed or removed a router and did not notice, because the proxy rule
        keeps looking plausible.
        """
        extra = sorted(_vite_prefixes() - _backend_prefixes())
        assert not extra, (
            f"vite.config.js proxies {extra}, which the backend does not serve. "
            "Either a router was renamed or removed, or this list is stale."
        )

    def test_monitoring_and_collect_are_proxied(self):
        """The two that were missed, pinned explicitly."""
        proxied = _vite_prefixes()
        assert "/monitoring" in proxied
        assert "/collect" in proxied

    def test_nginx_does_not_maintain_a_prefix_list(self):
        """nginx must stay self-maintaining.

        If someone re-adds per-router `location /prefix/` blocks, the drift
        problem returns with a third copy of the list to keep in sync. The only
        accepted shape is a `try_files` fallback to a named proxy location.
        """
        text = NGINX_CONF.read_text(encoding="utf-8")
        assert "try_files $uri $uri/ @backend;" in text, (
            "nginx.conf no longer uses the try_files fallback; it must not go "
            "back to enumerating backend routers."
        )
        per_router = re.findall(r"location\s+(/\w+/?)\s*\{\s*proxy_pass", text)
        assert not per_router, (
            f"nginx.conf re-introduced per-router proxy blocks for {per_router}. "
            "Use the try_files fallback instead."
        )