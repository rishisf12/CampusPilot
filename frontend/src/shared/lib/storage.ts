/**
 * Every localStorage key the app is allowed to use.
 *
 * The backend database is the source of truth for all real data, so this file
 * holds nothing but small UI state that would otherwise be lost on reload.
 * Centralising the keys here makes the rule auditable: if it is not in this
 * list, it does not belong in localStorage.
 */

const KEYS = {
  /** The JWT. Sent with every request; cleared only on a genuine 401. */
  token: 'auth_token',
  /** Cached user object, so the header can paint before /auth/me returns. */
  user: 'user',
  /** Refresh trigger: bumped after any profile or branch change. */
  profileVersion: 'profile_version',
  /** The last exam roll lookup (roll + results). */
  quickLookup: 'quick_lookup',
  /** Email awaiting OTP verification, with its resend cooldown timestamp. */
  pendingVerification: 'pending_verification_email',
  /** Flag that makes the sign-in page show "Email verified, please sign in". */
  emailJustVerified: 'email_just_verified',
};

/** Keys this app owns. Anything else in localStorage is left untouched. */
export const STORAGE_KEYS = Object.values(KEYS);

/**
 * Namespace for per-setting keys owned by the Settings bundle.
 *
 * A setting is written under `cp-setting:<key>` rather than as a bare key so it
 * can never collide with a session key, and so a whole user preference record
 * can be found (and later dropped) by prefix when settings move to the server.
 */
export const SETTING_PREFIX = 'cp-setting:';

export function settingStorageKey(key: string): string {
  return `${SETTING_PREFIX}${key}`;
}

/**
 * Read a key, tolerating storage being unavailable (private browsing, or a
 * browser that has blocked it). Never throws.
 */
export function readValue(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Write a key. `null` removes it. Never throws. */
export function writeValue(key: string, value: string | null | undefined): void {
  try {
    if (value === null || value === undefined || value === '') localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable - the session simply will not persist */
  }
}

/** Remove a key. Never throws. */
export function removeValue(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/** Read and parse a JSON key, returning `fallback` if absent or corrupt. */
export function readJson<T>(key: string, fallback: T | null = null): T | null {
  const raw = readValue(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    // A corrupt entry is worse than none: drop it so it cannot keep failing.
    removeValue(key);
    return fallback;
  }
}

/** Serialise and store a JSON value. Never throws. */
export function writeJson(key: string, value: unknown): void {
  try {
    writeValue(key, JSON.stringify(value));
  } catch {
    /* value not serialisable - nothing useful to cache */
  }
}

// ------------------------------------------------------------------ token

export function getToken(): string | null {
  return readValue(KEYS.token);
}

export function setToken(token: string): void {
  writeValue(KEYS.token, token);
}

/** Drop the session. Only ever called on a genuine 401 or an explicit logout. */
export function clearSession(): void {
  removeValue(KEYS.token);
  removeValue(KEYS.user);
  removeValue(KEYS.pendingVerification);
  removeValue(KEYS.emailJustVerified);
}

/**
 * Keys written by earlier versions of the app, or by the old backend.
 *
 * They held profile and lookup data that now lives on the server, so they are
 * removed once on start-up: leaving them would mean stale values shadowing the
 * real ones, and would keep this app's data in storage after the spec says it
 * must not be there.
 */
const OBSOLETE_KEYS = [
  'attendance_target', // target is on the profile now
  'exam_last_lookup', // superseded by `quick_lookup`
  'user_roll', // the roll comes from /auth/me
  'resend_available_at', // folded into `pending_verification_email`
  'campuspilot_token', // a leftover token store from before `auth_token`
  'timetable_file', // upload picks are no longer cached
  'exam_timetable_file',
  'exam_seating_file',
  // The theme was a bare localStorage key written by the header toggle. It is a
  // setting now, mirrored under `cp-setting:theme` so the first paint can read
  // it, and stored on the server so it follows the student between devices.
  'cp-theme',
];

/** Drop every obsolete key. Safe to call repeatedly. */
export function purgeObsoleteKeys(): void {
  OBSOLETE_KEYS.forEach(removeValue);
}

// ------------------------------------------------------------------- user

import type { UserResponse } from '../types/api';

export function readCachedUser(): UserResponse | null {
  return readJson<UserResponse>(KEYS.user, null);
}

export function writeCachedUser(user: UserResponse): void {
  writeJson(KEYS.user, user);
}

// ------------------------------------------------------------- quick lookup

import type { CachedExamLookup } from '../types/api';

export function readQuickLookup(): CachedExamLookup | null {
  return readJson<CachedExamLookup>(KEYS.quickLookup, null);
}

export function writeQuickLookup(value: CachedExamLookup | null): void {
  if (value === null) {
    removeValue(KEYS.quickLookup);
    return;
  }
  writeJson(KEYS.quickLookup, value);
}

// ------------------------------------------------- pending verification

/**
 * The pending signup email, with the resend cooldown timestamp kept alongside
 * it in the same record so both survive a reload together.
 *
 * Stored as JSON: `{ email, resendAvailableAt }`.
 */
export interface PendingVerificationRecord {
  email: string;
  resendAvailableAt: number;
}

export function readPendingVerification(): PendingVerificationRecord | null {
  const record = readJson<PendingVerificationRecord>(KEYS.pendingVerification, null);
  // Tolerate the older bare-email shape so an in-flight signup is not lost.
  if (typeof record === 'string') return { email: record, resendAvailableAt: 0 };
  return record && typeof record === 'object' ? record : null;
}

export function writePendingVerification(email: string, resendAvailableAt = 0): void {
  if (!email) {
    removeValue(KEYS.pendingVerification);
    return;
  }
  writeJson(KEYS.pendingVerification, { email, resendAvailableAt });
}

export function setResendAvailableAt(timestamp: number): void {
  const record = readPendingVerification() || { email: '', resendAvailableAt: 0 };
  writePendingVerification(record.email, timestamp);
}

export function readEmailJustVerified(): boolean {
  return readValue(KEYS.emailJustVerified) === '1';
}

export function setEmailJustVerified(): void {
  writeValue(KEYS.emailJustVerified, '1');
}

export function clearEmailJustVerified(): void {
  removeValue(KEYS.emailJustVerified);
}

// ---------------------------------------------------------- profile version

export function getProfileVersion(): number {
  const raw = Number(readValue(KEYS.profileVersion) || 0);
  return Number.isFinite(raw) ? raw : 0;
}

/**
 * Bump the shared profile version, then announce it.
 *
 * A same-tab `CustomEvent` is dispatched as well, because the `storage` event
 * only fires in *other* tabs - without it, the tab that made the edit would not
 * refetch.
 */
export function bumpProfileVersion(): void {
  // A timestamp, so two edits in the same millisecond still differ.
  const next = String(Date.now());
  writeValue(KEYS.profileVersion, next);
  try {
    window.dispatchEvent(new CustomEvent('profile-updated', { detail: { version: next } }));
  } catch {
    /* no window (tests) - the storage write is enough */
  }
}
