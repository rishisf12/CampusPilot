/**
 * API client — TypeScript version.
 *
 * Every request goes through the Vite proxy to the FastAPI backend on port 8000
 * and carries the stored JWT. A 401 is the *only* thing that clears the
 * session: network failures must not sign the user out, and a failed request
 * must never wipe data the user is already looking at.
 *
 * localStorage access is delegated to `./lib/storage`, which owns the list of
 * permitted keys.
 */

import {
  clearSession,
  getProfileVersion,
  getToken,
  setToken,
  bumpProfileVersion,
} from './lib/storage';

import type {
  UserResponse,
  TokenResponse,
  SignupRequest,
  VerifyEmailRequest,
  ResendCodeRequest,
  ProfileResponse,
  ProfileUpdate,
  ProfileOptions,
  BranchChangeRequest,
  ScheduleNowResponse,
  ExtraCourseResponse,
  ExtraCourseCreate,
  AttendanceRecordRequest,
  AttendanceRecord,
  AttendanceSummary,
  AttendanceSubject,
  AttendanceCourseDetail,
  TimetableSlot,
  TimetableOptions,
  ExamTimetableResponse,
  ExamSeatingResponse,
  ExamLookupResult,
  ExamClashesResponse,
  ExamStatus,
  VacantRoomResponse,
  FeedbackSubmit,
  FeedbackResponse,
  FeedbackReply,
  Team,
  TeamCreate,
  TeamDetail,
  TeamJoinRequest,
  TeamMatchResult,
  MyTeam,
  Hackathon,
  HackathonFeed,
  MonitoringSubsection,
  ValidationErrorDetail,
  HealthResponse,
} from './types/api';

const API_BASE = '';

export { clearSession, getToken, setToken, getProfileVersion, bumpProfileVersion };

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** True when the session should be dropped. */
export function isUnauthorized(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401;
}

/**
 * Turn an error body into one readable line.
 *
 * FastAPI answers a validation failure (422) with `detail` as a *list of
 * objects*, so joining it directly would render `[object Object]`. Each entry's
 * `msg` is the useful part; fall back to JSON for anything unrecognised.
 */
function formatDetail(detail: unknown): string {
  if (!Array.isArray(detail)) return String(detail);
  const parts = detail.map(item => {
    if (typeof item === 'string') return item;
    if (item && typeof item === 'object')
      return (item as ValidationErrorDetail).msg || JSON.stringify(item);
    return String(item);
  });
  return parts.join(', ') || 'Request failed';
}

/**
 * Options for `request`.
 *
 * `body` is widened to `unknown`: everything except FormData/URLSearchParams
 * is JSON-stringified below, so callers can pass a plain object without
 * casting it to `BodyInit` first.
 */
type RequestOptions = Omit<RequestInit, 'body'> & { body?: unknown };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers: optionHeaders, ...rest } = options;
  const headers: Record<string, string> = { ...(optionHeaders as Record<string, string>) };

  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload: BodyInit | null = body as BodyInit | null;
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  const isUrlEncoded = typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams;
  if (body && !isForm && !isUrlEncoded) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...rest, headers, body: payload });
  } catch {
    throw new ApiError('Backend offline', 0);
  }

  if (response.status === 204) return null as T;

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const detail =
      (data &&
        typeof data === 'object' &&
        (data as { detail?: unknown; message?: unknown }).detail) ||
      (data && typeof data === 'object' && (data as { message?: unknown }).message) ||
      (typeof data === 'string' && data) ||
      `Request failed (${response.status})`;
    throw new ApiError(formatDetail(detail), response.status);
  }

  return data as T;
}

function upload(path: string, file: File, extra: RequestOptions = {}): Promise<unknown> {
  const form = new FormData();
  form.append('file', file);
  return request(path, { method: 'POST', body: form, ...extra });
}

// ---------------------------------------------------------------- auth
export const authApi = {
  /**
   * Step 1 of registration: ask for a code, without creating anything yet.
   *
   * Always returns the same message whether or not the address is eligible, so
   * this cannot be used to find out who has an account here.
   */
  startSignup: (email: string) =>
    request<{ message: string }>('/auth/signup/start', { method: 'POST', body: { email } }),

  /** Step 2: confirm the code. This is what makes the address usable. */
  verifySignup: (email: string, code: string) =>
    request<{ message: string }>('/auth/signup/verify', { method: 'POST', body: { email, code } }),

  /** Step 3: create the account. Refused unless step 2 has been done. */
  signup: (data: SignupRequest) =>
    request<UserResponse>('/auth/signup', { method: 'POST', body: data }),

  verifyEmail: (data: VerifyEmailRequest) =>
    request<{ message: string }>('/auth/verify-email', { method: 'POST', body: data }),

  // The backend exposes this as /auth/resend-code and expects an object body.
  resendVerificationCode: (data: ResendCodeRequest) =>
    request<{ message: string }>('/auth/resend-code', { method: 'POST', body: data }),

  login: (username: string, password: string) => {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);
    return request<TokenResponse>('/auth/login', { method: 'POST', body: form });
  },

  me: () => request<UserResponse>('/auth/me'),

  logout: () => request<{ message: string }>('/auth/logout', { method: 'POST' }),

  /**
   * Ask for a password reset code.
   *
   * The response is the same whether or not the account exists, so this returns a
   * message and nothing else - there is deliberately no `sent: true/false` flag
   * to branch on.
   */
  forgotPassword: (identifier: string) =>
    request<{ message: string }>('/auth/forgot-password', { method: 'POST', body: { identifier } }),

  /** Set a new password from an emailed code. */
  resetPassword: (identifier: string, code: string, newPassword: string) =>
    request<{ message: string; passkeys_revoked?: number }>('/auth/reset-password', {
      method: 'POST',
      body: { identifier, code, new_password: newPassword },
    }),

  /**
   * The signed-in user's passkeys.
   *
   * Used to decide whether to offer enrolment after a first sign-in. The actual
   * WebAuthn exchange lives in `lib/passkey.ts`, which talks to the browser API
   * directly - it cannot go through `request` because the credential bytes must
   * not be stringified on the way out.
   */
  /** Matches the backend envelope: `{has_passkey, count, passkeys}`. */
  passkeys: () =>
    request<{
      has_passkey: boolean;
      count: number;
      passkeys: {
        credential_id: string;
        label: string;
        created_at: string | null;
        last_used_at: string | null;
      }[];
    }>('/auth/passkeys'),

  /**
   * Revoke a passkey, e.g. after losing the device that held it.
   *
   * The credential id is base64url, which contains characters a path segment
   * allows but that still need encoding to be safe in a URL.
   */
  removePasskey: (credentialId: string) =>
    request<{ message: string }>(`/auth/passkeys/${encodeURIComponent(credentialId)}`, {
      method: 'DELETE',
    }),
};

// ------------------------------------------------------------- profile
export const profileApi = {
  get: () => request<ProfileResponse>('/profile/'),
  update: (data: ProfileUpdate) =>
    request<ProfileResponse>('/profile/', { method: 'PUT', body: data }),
  options: () => request<ProfileOptions>('/profile/options'),
  requestBranchChange: (data: BranchChangeRequest) =>
    request<{ message: string }>('/profile/branch-change', { method: 'POST', body: data }),
  clearBranchChange: () =>
    request<{ message: string }>('/profile/branch-change', { method: 'DELETE' }),
};

// ------------------------------------------------------------ schedule
export const scheduleApi = {
  now: () => request<ScheduleNowResponse>('/schedule/now'),
  listExtra: () => request<ExtraCourseResponse[]>('/schedule/courses/extra'),
  addExtra: (data: ExtraCourseCreate) =>
    request<ExtraCourseResponse>('/schedule/courses/extra', { method: 'POST', body: data }),
  removeExtra: (code: string) =>
    request<{ message: string }>(`/schedule/courses/extra/${encodeURIComponent(code)}`, {
      method: 'DELETE',
    }),
};

// ----------------------------------------------------------- timetable
export const timetableApi = {
  upload: (file: File) => upload('/timetable/upload', file),
  options: () => request<TimetableOptions>('/timetable/options'),
  listSlots: () => request<TimetableSlot[]>('/timetable/slots'),
  clear: () => request<{ message: string }>('/timetable/', { method: 'DELETE' }),

  /** Metadata for the newest uploaded timetable, or `{ available: false }`. */
  latestUpload: () =>
    request<{ available: boolean; filename?: string; uploaded_at?: string; rows?: number }>(
      '/timetable/uploads/latest'
    ),

  /**
   * Object URL for the newest uploaded timetable, or `null` when there is none.
   *
   * The preview endpoint is authenticated, so it is fetched with the bearer token
   * and handed over as a blob: a plain link would go out without the
   * `Authorization` header and come back 401. The caller owns the returned URL
   * and must `URL.revokeObjectURL` it.
   */
  previewObjectUrl: async (): Promise<string | null> => {
    const token = getToken();
    if (!token) return null;
    const response = await fetch('/timetable/uploads/preview', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error('Could not load the preview');
    return URL.createObjectURL(await response.blob());
  },
};

// --------------------------------------------------------------- exam
export const examApi = {
  status: () => request<ExamStatus>('/exam/status'),
  uploadTimetable: (file: File) => upload('/exam/timetable/upload', file),
  uploadSeating: (file: File) => upload('/exam/seating/upload', file),
  getTimetable: () => request<ExamTimetableResponse>('/exam/timetable'),
  getSeating: () => request<ExamSeatingResponse>('/exam/seating'),
  lookup: (roll: string) =>
    request<ExamLookupResult>(`/exam/lookup?roll=${encodeURIComponent(roll)}`),
  clashes: (roll?: string) =>
    request<ExamClashesResponse>(`/exam/clashes${roll ? `?roll=${encodeURIComponent(roll)}` : ''}`),
  clearTimetable: () => request<{ message: string }>('/exam/timetable', { method: 'DELETE' }),
  clearSeating: () => request<{ message: string }>('/exam/seating', { method: 'DELETE' }),

  /** Metadata for the newest file uploaded to a section, or `{ available: false }`. */
  latestUpload: (kind: 'timetable' | 'seating') =>
    request<{ available: boolean; filename?: string; uploaded_at?: string; rows?: number }>(
      `/exam/uploads/latest?kind=${encodeURIComponent(kind)}`
    ),

  /**
   * Object URL for the newest uploaded file, or `null` when there is none.
   *
   * The preview endpoint is authenticated, so it is fetched with the bearer token
   * and handed over as a blob: a plain link or `window.open` would go out without
   * the `Authorization` header and come back 401. The caller owns the returned
   * URL and must `URL.revokeObjectURL` it.
   */
  previewObjectUrl: async (kind: 'timetable' | 'seating'): Promise<string | null> => {
    const token = getToken();
    if (!token) return null;
    const response = await fetch(`/exam/uploads/preview?kind=${encodeURIComponent(kind)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error('Could not load the preview');
    return URL.createObjectURL(await response.blob());
  },
};

// -------------------------------------------------------------- rooms
export const roomsApi = {
  vacant: (params: Record<string, unknown> = {}) => {
    const query = new URLSearchParams(
      Object.entries(params)
        .filter(([, value]) => value !== undefined && value !== null && value !== '')
        .map(([key, value]) => [key, String(value)] as [string, string])
    ).toString();
    return request<VacantRoomResponse>(`/rooms/vacant${query ? `?${query}` : ''}`);
  },
  all: () => request<string[]>('/rooms/all'),
};

// -------------------------------------------------------------- teams
function teamQuery(params: Record<string, unknown> = {}): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.append(key, String(value));
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

export const teamsApi = {
  list: (params: Record<string, unknown> = {}) =>
    request<{
      pagination: {
        total: number;
        page: number;
        size: number;
        pages: number;
        has_next: boolean;
        has_previous: boolean;
      };
      data: Team[];
    }>(`/teams${teamQuery(params)}`),
  matches: (params: Record<string, unknown> = {}) =>
    request<{ matches: TeamMatchResult[] }>(`/teams/match${teamQuery(params)}`),
  mine: () => request<{ teams: MyTeam[] }>('/teams/mine'),
  requests: () => request<{ requests: TeamJoinRequest[] }>('/teams/requests'),
  get: (id: number) => request<TeamDetail>(`/teams/${id}`),
  create: (data: TeamCreate) => request<Team>('/teams', { method: 'POST', body: data }),
  update: (id: number, data: Partial<TeamCreate>) =>
    request<Team>(`/teams/${id}`, { method: 'PUT', body: data }),
  remove: (id: number) => request<{ message: string }>(`/teams/${id}`, { method: 'DELETE' }),
  join: (id: number) =>
    request<{ status?: string; message?: string; detail?: string }>(`/teams/${id}/join`, {
      method: 'POST',
    }),
  leave: (id: number) => request<{ message: string }>(`/teams/${id}/leave`, { method: 'POST' }),
  respond: (requestId: number, status: 'accepted' | 'rejected') =>
    request<{ message: string }>(`/teams/requests/${requestId}`, {
      method: 'PUT',
      body: { status },
    }),
};

// ---------------------------------------------------------- hackathons
export const hackathonsApi = {
  list: (params: Record<string, unknown> = {}) =>
    request<HackathonFeed>(`/hackathons${teamQuery(params)}`),
  create: (data: Partial<Hackathon>) =>
    request<Hackathon>('/hackathons', { method: 'POST', body: data }),
  /** Pull new mail and sweep anything past the retention window. */
  sync: () =>
    request<{ ok: boolean; added: number; reason?: string }>('/hackathons/feed/sync', {
      method: 'POST',
    }),
};

// ---------------------------------------------------------- attendance
// The backend serves subjects/summary/records/course and the sync trigger.
// The banner, history, per-subject "today" state, calendar and attendance
// target are derived on the client from these.
export const attendanceApi = {
  summary: () => request<AttendanceSummary>('/attendance/summary'),
  subjects: () => request<{ count: number; subjects: AttendanceSubject[] }>('/attendance/subjects'),
  records: (courseId?: number) =>
    request<AttendanceRecord[]>(`/attendance/records${courseId ? `?course_id=${courseId}` : ''}`),
  course: (id: number) => request<AttendanceCourseDetail>(`/attendance/course/${id}`),
  mark: (data: AttendanceRecordRequest) =>
    request<AttendanceRecord>('/attendance/', { method: 'POST', body: data }),
  remove: (id: number) => request<{ message: string }>(`/attendance/${id}`, { method: 'DELETE' }),
  sync: () => request<{ synced: number }>('/attendance/sync'),
};

// ---------------------------------------------------------- feedback
export const feedbackApi = {
  /**
   * Submit feedback text with an optional file.
   *
   * Sent as multipart FormData so the attachment rides along with the fields.
   * Name/phone/email fall back to the profile on the server, so only the
   * message is required here.
   */
  submit: ({ message, name, phone, email, subject, file }: FeedbackSubmit) => {
    const form = new FormData();
    form.append('message', message);
    if (name) form.append('name', name);
    if (phone) form.append('phone', phone);
    if (email) form.append('email', email);
    if (subject) form.append('subject', subject);
    if (file) form.append('file', file);
    return request<FeedbackResponse>('/feedback/', { method: 'POST', body: form });
  },

  /** The signed-in student's own submissions, newest first. */
  mine: () => request<FeedbackResponse[]>('/feedback/mine'),

  /** Every response, newest first. Admin-only; backs the admin responses view. */
  responses: () => request<FeedbackResponse[]>('/feedback/responses'),

  /** Answer one feedback as admin. Appears under the student's entry. */
  reply: (id: number, message: string) =>
    request<FeedbackReply>(`/feedback/${id}/reply`, { method: 'POST', body: { message } }),

  /** Check if mail ingestion is configured. */
  ingestStatus: () => request<{ configured: boolean }>('/feedback/ingest/status'),
};

// ------------------------------------------------------------- health
export const healthApi = {
  check: () => request<HealthResponse>('/health'),
};

// ------------------------------------------------------------ monitoring
//
// The admin reads behind both monitoring sections. Every call here is a GET
// except `rollup` and the scan triggers, and the subsection list comes from
// the server rather than being duplicated in the UI - a hardcoded copy would
// eventually disagree with the backend's allowlist and produce a button that
// always fails with no obvious cause.
export const monitoringApi = {
  subsections: () => request<{ subsections: MonitoringSubsection[] }>('/monitoring/subsections'),

  /** Everything the panels need, one round trip, one consistent window. */
  overview: (days = 7, platform: string | null = null) => {
    const search = new URLSearchParams({ days: String(days) });
    if (platform) search.set('platform', platform);
    return request<unknown>(`/monitoring/overview?${search}`);
  },

  health: (days = 7, platform = 'web') =>
    request<unknown>(`/monitoring/health?days=${days}&platform=${platform}`),

  history: (subsection: string | null = null, limit = 50) => {
    const search = new URLSearchParams({ limit: String(limit) });
    if (subsection) search.set('subsection', subsection);
    return request<unknown>(`/monitoring/history?${search}`);
  },

  /** Subsection D: volume, sentiment and topic mix. Read-only. */
  feedback: (days = 30) => request<unknown>(`/monitoring/feedback?days=${days}`),

  /** Purchases and ad revenue, with the verified/unverified split. */
  monetisation: (days = 30) => request<unknown>(`/monitoring/monetisation?days=${days}`),

  /** Rebuild the hourly rollup now, instead of waiting for the timer. */
  rollup: (lookbackHours = 48) =>
    request<{ rows_written: number; events_scanned: number }>(
      `/monitoring/rollup?lookback_hours=${lookbackHours}`,
      { method: 'POST' }
    ),
};

// ------------------------------------------------------------ telemetry
//
// The client-side beacon. Fire-and-forget by design: nothing in the UI waits
// on it, and a failure must never surface to a student. `navigator.sendBeacon`
// is used where available because it survives the page unloading, which is
// exactly when `session_end` and `page_view` fire and exactly when a normal
// fetch would be cancelled mid-flight.
export const telemetryApi = {
  /** The beacon. Resolves either way; never throws. */
  send(events: Array<Record<string, unknown>>) {
    const payload = JSON.stringify({
      platform: 'web',
      events: events.slice(0, 20),
    });
    try {
      if (navigator.sendBeacon) {
        // sendBeacon returns false when the browser refuses the payload
        // (usually a size cap). Falling back to fetch with keepalive covers
        // that case; without the fallback, events over the cap are lost.
        if (
          navigator.sendBeacon('/collect/events', new Blob([payload], { type: 'application/json' }))
        )
          return Promise.resolve(true);
      }
      fetch('/collect/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
        // The collector is deliberately open, so the beacon must never carry
        // the JWT: a token on a beacon URL ends up in browser history and in
        // any proxy log, and the endpoint does not need it.
      }).catch(() => false);
      return Promise.resolve(true);
    } catch {
      return Promise.resolve(false);
    }
  },
};
