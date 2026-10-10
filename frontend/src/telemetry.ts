/**
 * Web telemetry: session lifecycle, page views, and crash capture.
 *
 * Fire-and-forget by design — nothing in the UI waits on it and no failure
 * may ever surface to a student. Payloads mirror the backend collector
 * contract (`features/monitoring/infrastructure/collector.py`):
 *
 *   POST /collect/events   session_start / page_view / session_end
 *   POST /collect/crash    uncaught errors + unhandled rejections
 *
 * Privacy: no user id, no IP, no query strings (they carry roll numbers),
 * no free-text props. The session id is a random per-tab token in
 * sessionStorage and dies with the tab.
 */
import { telemetryApi } from './api';
import pkg from '../package.json';

const APP_VERSION: string = pkg.version;
const PLATFORM = 'web';
/** One page load should not become a crash storm against the rate limiter. */
const MAX_CRASHES_PER_PAGE = 10;

type DeviceInfo = { osVersion: string; deviceModel: string };

/** Per-tab session id: 8–64 chars per the collector's validation. */
function getSid(): string {
  const KEY = 'cp_session_id';
  try {
    const existing = sessionStorage.getItem(KEY);
    if (existing && existing.length >= 8) return existing;
    const id =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID().replace(/-/g, '')
        : Math.random().toString(16).slice(2) + Date.now().toString(16);
    sessionStorage.setItem(KEY, id);
    return id;
  } catch {
    // Storage blocked (private mode / disabled cookies): a throwaway id still
    // lets the events land; it just cannot be joined across reloads.
    return Date.now().toString(16).padStart(16, '0') + Math.random().toString(16).slice(2, 10);
  }
}

/**
 * Second-precision ISO8601. The fractional seconds are deliberately stripped:
 * the backend parses with `datetime.fromisoformat`, which rejects the 3-digit
 * milliseconds `toISOString()` produces on older Python, and Android sends
 * the same second-precision format.
 */
function nowIso(): string {
  return new Date().toISOString().replace(/\.\d+Z$/, 'Z');
}

/**
 * `os_version` is validated against `[A-Za-z0-9._+-]{1,32}` (no spaces), so
 * the OS is a single token; `device_model` is free text and carries the
 * browser, which is the "device" a web app actually runs on.
 */
function deviceInfo(): DeviceInfo {
  const ua = navigator.userAgent;
  let osVersion = 'Unknown';
  if (/Windows/i.test(ua)) osVersion = 'Windows';
  else if (/Android/i.test(ua)) osVersion = 'Android';
  else if (/iPhone|iPad|iPod/i.test(ua)) osVersion = 'iOS';
  else if (/Mac OS X/i.test(ua)) osVersion = 'macOS';
  else if (/CrOS/i.test(ua)) osVersion = 'ChromeOS';
  else if (/Linux/i.test(ua)) osVersion = 'Linux';

  const pick = (re: RegExp, name: string): string | null => {
    const m = ua.match(re);
    return m ? `${name} ${m[1].split('.')[0]}` : null;
  };
  const deviceModel =
    pick(/Edg\/(\d+)/, 'Edge') ??
    pick(/OPR\/(\d+)/, 'Opera') ??
    pick(/Firefox\/(\d+)/, 'Firefox') ??
    pick(/Chrome\/(\d+)/, 'Chrome') ??
    pick(/Version\/(\d+).*Safari/, 'Safari') ??
    'Browser';

  return { osVersion, deviceModel };
}

function baseEvent(eventName: string, props?: Record<string, string>) {
  const { osVersion, deviceModel } = deviceInfo();
  return {
    event_name: eventName,
    platform: PLATFORM,
    session_id: getSid(),
    ts: nowIso(),
    app_version: APP_VERSION,
    os_version: osVersion,
    device_model: deviceModel,
    ...(props ? { props } : {}),
  };
}

// ---------------------------------------------------------------- crashes

const reportedFingerprints = new Set<string>();

/**
 * Fingerprint = exception type + top stack frames, hashed. The message and
 * line numbers are excluded on purpose: they vary between builds and would
 * shatter one bug into a dozen clusters (same reasoning as the Android
 * client's fingerprint).
 */
async function fingerprintOf(type: string, stack: string): Promise<string> {
  const frames = stack.split('\n').slice(1, 9).join('\n');
  const material = `${type}\n${frames}`;
  try {
    if (typeof crypto !== 'undefined' && crypto.subtle) {
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(material));
      return Array.from(new Uint8Array(digest))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    }
  } catch {
    // Fall through to the non-crypto hash (crypto.subtle is undefined on
    // insecure origins other than localhost).
  }
  let h = 0x811c9dc5;
  for (let i = 0; i < material.length; i++) {
    h ^= material.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return `fnv${h.toString(16)}`;
}

/**
 * A page-level "crash" for the web is an exception nothing caught. `fatal`
 * distinguishes the two sources: an uncaught synchronous error means a render
 * path is broken (it counts against the crash-free rate), while an unhandled
 * rejection frequently leaves the page fully usable, so it is recorded and
 * clustered but kept out of the fatal denominator.
 */
function recordCrash(error: unknown, fallbackMessage: string | undefined, fatal: boolean) {
  try {
    const err = error instanceof Error ? error : null;
    const type = err?.name ?? 'Error';
    const message = (err?.message ?? fallbackMessage ?? String(error ?? 'Unknown error')).slice(
      0,
      4000
    );
    const stack = (err?.stack ?? '').slice(0, 8000);

    void fingerprintOf(type, stack).then(fingerprint => {
      if (reportedFingerprints.has(fingerprint)) return;
      if (reportedFingerprints.size >= MAX_CRASHES_PER_PAGE) return;
      reportedFingerprints.add(fingerprint);

      const { osVersion, deviceModel } = deviceInfo();
      fetch('/collect/crash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // keepalive lets the request outlive the page when possible.
        keepalive: true,
        body: JSON.stringify({
          platform: PLATFORM,
          kind: 'crash',
          session_id: getSid(),
          fingerprint,
          fatal,
          foreground: true,
          exception_type: type,
          message,
          stack_trace: stack || null,
          app_version: APP_VERSION,
          os_version: osVersion,
          device_model: deviceModel,
        }),
      }).catch(() => {
        // Telemetry failure must never surface in the UI.
      });
    });
  } catch {
    // Same rule: never let the reporter itself throw.
  }
}

// ---------------------------------------------------------------- lifecycle

function initSession(): void {
  telemetryApi.send([
    baseEvent('session_start'),
    baseEvent('page_view', { path: location.pathname }),
  ]);

  // sendBeacon survives unloading — the one moment a normal fetch dies.
  window.addEventListener('pagehide', () => {
    telemetryApi.send([baseEvent('session_end')]);
  });

  window.addEventListener('error', ev => {
    // Resource load failures (img/script/css) arrive here with no Error
    // object — that is a network problem, not a JS crash.
    if (!ev.error && !ev.message) return;
    recordCrash(ev.error, ev.message, true);
  });

  window.addEventListener('unhandledrejection', (ev: PromiseRejectionEvent) => {
    recordCrash(ev.reason, 'Unhandled promise rejection', false);
  });
}

initSession();
