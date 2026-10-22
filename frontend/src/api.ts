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
} from './shared/lib/storage';
import type { SettingsValue } from './shared/constants';

import type {
  UserResponse,
  TokenResponse,
  SignupRequest,
  VerifyEmailRequest,
  ResendCodeRequest,
  ProfileResponse,
  ProfileUpdate,
  ProfileOptions,
  AdminProfileResponse,
  AdminProfileUpdate,
  AdminActivityItem,
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
  ExamOptions,
  ExamSlotResponse,
  ExamSlotEdit,
  VacantRoomResponse,
  FeedbackSubmit,
  FeedbackResponse,
  FeedbackReply,
  MonitoringSubsection,
  ValidationErrorDetail,
  HealthResponse,
  OpportunityDetail,
  OpportunityListItem,
  OpportunityDetailAdmin,
  PaginatedOpportunities,
  FeedFilters,
  OpportunityFilterParams,
  OpportunityUpdateRequest,
  BulkActionRequest,
  StateTransitionRequest,
  RunListItem,
  RunResponse,
  RunCreateRequest,
  AgentSettingsResponse,
  AgentSettingsUpdateRequest,
  SourceRuleResponse,
  SourceRuleCreateRequest,
  SourceRuleUpdateRequest,
  SearchQueryResponse,
  SearchQueryCreateRequest,
  SearchQueryUpdateRequest,
  LLMStatusResponse,
  LLMTestRequest,
  LLMTestResponse,
  OppFeedFeedbackResponse,
  OppFeedFeedbackCreateRequest,
} from './shared/types/api';

/** Query parameters for the mail list; all optional. */
export interface MailListParams {
  section?: string;
  search?: string;
  starred?: boolean;
  direction?: string;
  group?: string;
  page?: number;
  size?: number;
}

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

// ---------------------------------------------------------- admin profile
//
// The administrator's own profile. A separate surface from the student one
// on purpose: an operator has no roll number, no branch and no elective
// list, and their screen says what an operator actually works with.
export const adminProfileApi = {
  get: () => request<AdminProfileResponse>('/profile/admin'),
  update: (data: AdminProfileUpdate) =>
    request<AdminProfileResponse>('/profile/admin', { method: 'PUT', body: data }),
  activity: (limit = 25) => request<AdminActivityItem[]>(`/profile/admin/activity?limit=${limit}`),
};

// ------------------------------------------------------------ settings
//
// The Settings page's own endpoints. The key names and their types live in the
// settings registry, not here: the server stores the document it is given, so
// this client passes values through without knowing what any of them mean.
export const settingsApi = {
  get: () =>
    request<{ settings: Record<string, SettingsValue> }>('/settings').then(r => r.settings),
  update: (patch: Record<string, SettingsValue | null>) =>
    request<{ settings: Record<string, SettingsValue> }>('/settings', {
      method: 'PATCH',
      body: { settings: patch },
    }).then(r => r.settings),
  clear: () =>
    request<{ settings: Record<string, SettingsValue> }>('/settings', { method: 'DELETE' }).then(
      r => r.settings
    ),
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

  /** Branch / semester / course options discovered in the uploaded exam data. */
  options: () => request<ExamOptions>('/exam/options'),

  /** List all exam timetable slots (ungrouped, for editing). */
  listSlots: () => request<ExamSlotResponse[]>('/exam/slots'),

  /** Edit a single exam timetable slot. */
  editSlot: (slot_id: number, data: ExamSlotEdit) =>
    request<ExamSlotResponse>(`/exam/slot/${slot_id}`, { method: 'PUT', body: data }),

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

// ------------------------------------------------- reinforcement patterns
export interface ReinforcementPattern {
  id: number;
  name: string;
  pattern: string;
  replacement: string;
  description: string;
  enabled: boolean;
}

export const reinforcementApi = {
  list: () => request<ReinforcementPattern[]>('/reinforcement/'),
  create: (data: { name: string; pattern: string; replacement: string; description: string }) =>
    request<{ id: number; message: string }>('/reinforcement/', {
      method: 'POST',
      body: data,
    }),
  update: (
    id: number,
    data: {
      name?: string;
      pattern?: string;
      replacement?: string;
      description?: string;
      enabled?: boolean;
    }
  ) =>
    request<{ message: string }>(`/reinforcement/${id}`, {
      method: 'PUT',
      body: data,
    }),
  remove: (id: number) =>
    request<{ message: string }>(`/reinforcement/${id}`, { method: 'DELETE' }),
  test: (data: { pattern: string; replacement: string; text: string }) =>
    request<{ input: string; output: string; matched: boolean }>('/reinforcement/test', {
      method: 'POST',
      body: data,
    }),
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

// ---------------------------------------------------------------- admin
export interface AdminUser {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  roll_number: string | null;
  role: string;
  is_email_verified: boolean;
  created_at: string | null;
  /** The profile's own fields: what the list filters on. */
  programme?: string | null;
  semester?: number | null;
  branch?: string | null;
  section?: string | null;
  batch_year?: number | null;
  is_faculty?: boolean;
  is_class_representative?: boolean;
}

/** The values the admin's user list can be filtered by. */
export interface AdminUserFilters {
  batch_years: number[];
  branches: string[];
  semesters: number[];
}

export interface AdminFlag {
  id: number;
  key: string;
  name: string;
  description: string | null;
  enabled: boolean;
  rollout_percentage: number;
  target_roles: string[];
  target_user_ids: number[];
  target_platforms: string[];
  target_app_versions: string[];
  target_rules: { attribute: string; operator: string; values: string[] }[];
  created_at: string;
  updated_at: string;
}

export interface AdminMaintenanceWindow {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
  global_maintenance: boolean;
  target_features: string[];
  message: string | null;
  allow_list_user_ids: number[];
  bypass_roles: string[];
  scheduled_start: string | null;
  scheduled_end: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminRemoteConfig {
  id: number;
  key: string;
  value: Record<string, unknown>;
  value_type: string;
  description: string | null;
  schema_json: Record<string, unknown> | null;
  schema_version: number;
  is_public: boolean;
  updated_by: number | null;
  updated_at: string;
}

export const adminApi = {
  users: (
    params: {
      search?: string;
      role?: string;
      category?: string;
      group?: string;
      programme?: string;
      batch_year?: number;
      branch?: string;
      semester?: number;
      page?: number;
      size?: number;
    } = {}
  ) => {
    const search = new URLSearchParams();
    if (params.search) search.set('search', params.search);
    if (params.role) search.set('role', params.role);
    if (params.category) search.set('category', params.category);
    if (params.group) search.set('group', params.group);
    if (params.programme) search.set('programme', params.programme);
    if (params.batch_year) search.set('batch_year', String(params.batch_year));
    if (params.branch) search.set('branch', params.branch);
    if (params.semester) search.set('semester', String(params.semester));
    search.set('page', String(params.page ?? 1));
    search.set('size', String(params.size ?? 20));
    return request<{ total: number; page: number; size: number; users: AdminUser[] }>(
      `/admin/users?${search}`
    );
  },
  userFilters: () => request<AdminUserFilters>('/admin/users/filters'),
  updateUser: (
    id: number,
    data: {
      programme?: string;
      semester?: number;
      branch?: string;
      section?: string;
      batch_year?: number;
      is_faculty?: boolean;
      is_class_representative?: boolean;
    }
  ) => request<AdminUser>(`/admin/users/${id}`, { method: 'PATCH', body: data }),
  setRole: (id: number, role: 'admin' | 'student') =>
    request<AdminUser>(`/admin/users/${id}/role`, { method: 'PATCH', body: { role } }),
  stats: () =>
    request<{ total: number; admins: number; students: number; verified: number }>('/admin/stats'),
  exportSubsection: (subsection: string, days = 30, format: 'json' | 'csv' = 'json') =>
    request<unknown>(`/monitoring/export/${subsection}?days=${days}&format=${format}`),

  // Feature Flags
  flags: () =>
    request<{ total: number; page: number; size: number; flags: AdminFlag[] }>('/admin/flags'),
  createFlag: (data: {
    key: string;
    name: string;
    description?: string;
    enabled?: boolean;
    rollout_percentage?: number;
    target_roles?: string[];
    target_user_ids?: number[];
    target_platforms?: string[];
    target_app_versions?: string[];
    target_rules?: { attribute: string; operator: string; values: string[] }[];
  }) => request<AdminFlag>('/admin/flags', { method: 'POST', body: data }),
  getFlag: (key: string) => request<AdminFlag>(`/admin/flags/${key}`),
  updateFlag: (key: string, data: Partial<AdminFlag>) =>
    request<AdminFlag>(`/admin/flags/${key}`, { method: 'PATCH', body: data }),
  deleteFlag: (key: string) => request<void>(`/admin/flags/${key}`, { method: 'DELETE' }),

  // Maintenance
  maintenance: () =>
    request<{ total: number; page: number; size: number; windows: AdminMaintenanceWindow[] }>(
      '/admin/maintenance'
    ),
  createMaintenance: (data: {
    name: string;
    description?: string;
    global_maintenance?: boolean;
    target_features?: string[];
    message?: string;
    allow_list_user_ids?: number[];
    bypass_roles?: string[];
    scheduled_start?: string;
    scheduled_end?: string;
  }) => request<AdminMaintenanceWindow>('/admin/maintenance', { method: 'POST', body: data }),
  getMaintenance: (id: number) => request<AdminMaintenanceWindow>(`/admin/maintenance/${id}`),
  updateMaintenance: (id: number, data: Partial<AdminMaintenanceWindow>) =>
    request<AdminMaintenanceWindow>(`/admin/maintenance/${id}`, { method: 'PATCH', body: data }),
  deleteMaintenance: (id: number) =>
    request<void>(`/admin/maintenance/${id}`, { method: 'DELETE' }),

  // Remote Config
  remoteConfigs: (publicOnly = false) =>
    request<{ total: number; page: number; size: number; configs: AdminRemoteConfig[] }>(
      `/admin/remote-config?public_only=${publicOnly}`
    ),
  createRemoteConfig: (data: {
    key: string;
    value: Record<string, unknown>;
    value_type?: string;
    description?: string;
    schema_json?: Record<string, unknown>;
    schema_version?: number;
    is_public?: boolean;
  }) => request<AdminRemoteConfig>('/admin/remote-config', { method: 'POST', body: data }),
  getRemoteConfig: (key: string) => request<AdminRemoteConfig>(`/admin/remote-config/${key}`),
  updateRemoteConfig: (key: string, data: Partial<AdminRemoteConfig>) =>
    request<AdminRemoteConfig>(`/admin/remote-config/${key}`, { method: 'PATCH', body: data }),
  deleteRemoteConfig: (key: string) =>
    request<void>(`/admin/remote-config/${key}`, { method: 'DELETE' }),
  rollbackRemoteConfig: (key: string, version: number) =>
    request<AdminRemoteConfig>(`/admin/remote-config/${key}/rollback`, {
      method: 'POST',
      body: { version },
    }),
  getRemoteConfigHistory: (key: string, limit = 50) =>
    request<{
      history: Array<{
        schema_version: number;
        value: unknown;
        value_type: string;
        changed_by: number | null;
        change_reason: string | null;
        created_at: string;
      }>;
    }>(`/admin/remote-config/${key}/history?limit=${limit}`),

  // Errors
  errors: () =>
    request<{
      errors: Array<{
        fingerprint: string;
        message: string;
        status: string;
        count: number;
        first_seen: string;
        last_seen: string;
        assignee: string | null;
      }>;
    }>('/admin/errors'),

  // Analytics
  analyticsOverview: (days = 7) =>
    request<{
      dau: number;
      wau: number;
      mau: number;
      retention_d7: number;
      new_signups: number;
      verified_rate: number;
    }>(`/admin/analytics/overview?days=${days}`),
  featureUsage: (days = 7) =>
    request<Array<{ feature: string; unique_users: number; opens: number; platform: string }>>(
      `/admin/analytics/feature-usage?days=${days}`
    ),
  retention: (days = 7) =>
    request<{ d1: number; d7: number; d30: number }>(`/admin/analytics/retention?days=${days}`),
  platformVersions: (days = 7) =>
    request<Array<{ platform: string; version: string; unique_users: number; count: number }>>(
      `/admin/analytics/platforms?days=${days}`
    ),
  runAggregation: (date?: string) =>
    request<{ date: string; aggregations: Array<{ metric: string; count: number }> }>(
      `/admin/analytics/aggregate/daily${date ? `?date=${date}` : ''}`,
      { method: 'POST' }
    ),
  detectAnomalies: (date?: string) =>
    request<{
      detected: number;
      anomalies: Array<{
        metric: string;
        expected: number;
        actual: number;
        deviation_pct: number;
        severity: string;
      }>;
    }>(`/admin/analytics/anomalies/detect${date ? `?date=${date}` : ''}`, { method: 'POST' }),
  getEvents: (
    params: {
      event_name?: string;
      user_id?: number;
      platform?: string;
      since?: string;
      until?: string;
      limit?: number;
    } = {}
  ) => {
    const search = new URLSearchParams();
    if (params.event_name) search.set('event_name', params.event_name);
    if (params.user_id) search.set('user_id', String(params.user_id));
    if (params.platform) search.set('platform', params.platform);
    if (params.since) search.set('since', params.since);
    if (params.until) search.set('until', params.until);
    if (params.limit) search.set('limit', String(params.limit));
    return request<{
      events: Array<{
        id: number;
        event_name: string;
        user_id: number | null;
        platform: string;
        app_version: string | null;
        properties: unknown | null;
        created_at: string;
      }>;
    }>(`/admin/analytics/events?${search}`);
  },
  trackEvent: (data: {
    event_name: string;
    user_id?: number;
    session_id?: string;
    platform?: string;
    app_version?: string;
    properties?: Record<string, unknown>;
  }) =>
    request<{ id: number; event_name: string; created_at: string }>('/admin/analytics/track', {
      method: 'POST',
      body: data,
    }),
  trackBatch: (
    events: Array<{
      event_name: string;
      user_id?: number;
      session_id?: string;
      platform?: string;
      app_version?: string;
      properties?: Record<string, unknown>;
    }>
  ) =>
    request<{ tracked: number }>('/admin/analytics/track/batch', {
      method: 'POST',
      body: { events },
    }),

  // Segments
  segments: (isActive?: boolean) => {
    const search = new URLSearchParams();
    if (isActive !== undefined) search.set('is_active', String(isActive));
    return request<{
      segments: Array<{
        id: number;
        name: string;
        description: string | null;
        criteria_json: Record<string, unknown>;
        is_active: boolean;
        created_at: string;
        updated_at: string;
      }>;
    }>(`/admin/analytics/segments?${search}`);
  },
  createSegment: (data: {
    name: string;
    description?: string;
    criteria_json: Record<string, unknown>;
  }) =>
    request<{
      id: number;
      name: string;
      criteria_json: Record<string, unknown>;
      is_active: boolean;
      created_at: string;
    }>('/admin/analytics/segments', { method: 'POST', body: data }),
  getSegment: (id: number) =>
    request<{
      id: number;
      name: string;
      description: string | null;
      criteria_json: Record<string, unknown>;
      is_active: boolean;
      created_at: string;
      updated_at: string;
    }>(`/admin/analytics/segments/${id}`),
  updateSegment: (
    id: number,
    data: {
      name?: string;
      description?: string;
      criteria_json?: Record<string, unknown>;
      is_active?: boolean;
    }
  ) =>
    request<{
      id: number;
      name: string;
      criteria_json: Record<string, unknown>;
      is_active: boolean;
      updated_at: string;
    }>(`/admin/analytics/segments/${id}`, { method: 'PATCH', body: data }),
  deleteSegment: (id: number) =>
    request<void>(`/admin/analytics/segments/${id}`, { method: 'DELETE' }),
  segmentUsers: (segmentId: number) =>
    request<{ segment_id: number; user_count: number; user_ids: number[] }>(
      `/admin/analytics/segments/${segmentId}/users`
    ),

  // Funnels
  funnels: (isActive?: boolean) => {
    const search = new URLSearchParams();
    if (isActive !== undefined) search.set('is_active', String(isActive));
    return request<{
      funnels: Array<{
        id: number;
        name: string;
        description: string | null;
        steps: string[];
        window_hours: number;
        is_active: boolean;
        created_at: string;
        updated_at: string;
      }>;
    }>(`/admin/analytics/funnels?${search}`);
  },
  createFunnel: (data: {
    name: string;
    description?: string;
    steps: string[];
    window_hours?: number;
  }) =>
    request<{
      id: number;
      name: string;
      description: string | null;
      steps: string[];
      window_hours: number;
      created_at: string;
    }>('/admin/analytics/funnels', { method: 'POST', body: data }),
  analyzeFunnel: (id: number, days = 7) =>
    request<{
      funnel_id: number;
      name: string;
      steps: Array<{ step: string; users: number; conversion: number }>;
    }>(`/admin/analytics/funnels/${id}/analyze?days=${days}`),

  // Anomalies
  anomalies: (status?: string, severity?: string, days = 7) => {
    const search = new URLSearchParams();
    if (status) search.set('status', status);
    if (severity) search.set('severity', severity);
    search.set('days', String(days));
    return request<{
      anomalies: Array<{
        id: number;
        metric_name: string;
        dimension: string | null;
        dimension_value: string | null;
        expected_value: number;
        actual_value: number;
        deviation_pct: number;
        severity: string;
        description: string;
        status: string;
        detected_at: string;
      }>;
    }>(`/admin/analytics/anomalies?${search}`);
  },
  updateAnomaly: (id: number, status: string) =>
    request<{ id: number; status: string }>(`/admin/analytics/anomalies/${id}`, {
      method: 'PATCH',
      body: { status },
    }),

  // The backend serves this under /admin/analytics/users/{id}/360, where the
  // analytics service (events, errors, profile joins) lives - not under
  // /admin/users. An earlier revision of this path 404d on every lookup.
  user360: (id: string) =>
    request<{
      user: {
        id: number;
        email: string;
        username: string;
        full_name: string | null;
        roll_number: string | null;
        role: string;
        is_email_verified: boolean;
        created_at: string | null;
      };
      profile: {
        full_name: string | null;
        phone: string | null;
        branch: string | null;
        semester: number | null;
        programme: string | null;
      } | null;
      recent_events: Array<{ event_name: string; platform: string; created_at: string }>;
      teams: number[];
      recent_errors: Array<{ fingerprint: string; platform: string; created_at: string }>;
    }>(`/admin/analytics/users/${id}/360`),

  // Security
  securityEvents: () =>
    request<{
      events: Array<{
        type: string;
        severity: string;
        actor_email: string | null;
        actor_id: number | null;
        details: string | null;
        ip_hash: string | null;
        created_at: string;
      }>;
    }>('/admin/security/events'),

  // Audit
  auditLogs: (
    params: {
      search?: string;
      action?: string;
      actor_id?: number;
      target_type?: string;
      target_id?: string;
      page?: number;
      size?: number;
    } = {}
  ) => {
    const search = new URLSearchParams();
    if (params.search) search.set('search', params.search);
    if (params.action) search.set('action', params.action);
    if (params.actor_id) search.set('actor_id', String(params.actor_id));
    if (params.target_type) search.set('target_type', params.target_type);
    if (params.target_id) search.set('target_id', params.target_id);
    search.set('page', String(params.page ?? 1));
    search.set('size', String(params.size ?? 50));
    return request<{
      total: number;
      page: number;
      size: number;
      logs: Array<{
        id: number;
        actor_id: number | null;
        actor_email: string | null;
        actor_role: string | null;
        action: string;
        target_type: string | null;
        target_id: string | null;
        before_json: unknown | null;
        after_json: unknown | null;
        ip_hash: string | null;
        user_agent_hash: string | null;
        request_id: string | null;
        created_at: string;
      }>;
    }>(`/admin/audit?${search}`);
  },
  exportAuditLogs: (
    params: {
      search?: string;
      action?: string;
      actor_id?: number;
      target_type?: string;
      target_id?: string;
      format?: 'json' | 'csv';
    } = {}
  ) => {
    const search = new URLSearchParams();
    if (params.search) search.set('search', params.search);
    if (params.action) search.set('action', params.action);
    if (params.actor_id) search.set('actor_id', String(params.actor_id));
    if (params.target_type) search.set('target_type', params.target_type);
    if (params.target_id) search.set('target_id', params.target_id);
    if (params.format) search.set('format', params.format);
    return request<Blob>(`/admin/audit/export?${search}`);
  },

  // Settings
  getSettings: () => request<Record<string, unknown>>('/admin/settings'),
  updateSetting: (key: string, value: unknown) =>
    request<{ key: string; value: unknown }>(`/admin/settings/${key}`, {
      method: 'PATCH',
      body: { value },
    }),
};

// ------------------------------------------------------------ monitoring
//
// The admin Monitoring tab reads the MCP layer's panel endpoints. Every
// figure it shows comes through the same tool registry the scan agent uses:
// redacted, subsection-scoped and audited. What is left under `/monitoring`
// is what MCP has no equivalent for - the scan history, the rollup trigger
// and the raw export - and those live in `monitoringApi` below.
export interface ScanResultResponse {
  scan_id: string;
  subsection: string;
  status: 'healthy' | 'warning' | 'critical' | 'error';
  summary: string;
  findings: Array<{ title: string; severity: string; evidence: unknown[] }>;
  root_causes: string[];
  actions: Array<{ action: string; priority: number; detail: string }>;
  confidence: { level?: string; missing_data?: string[]; tools_failed?: string[] };
  window_start: string;
  window_end: string;
  duration_ms: number;
  /** The provider and model that answered. */
  model: string;
  created_at: string;
}

/**
 * The MCP panel surface - the admin Monitoring tab's data and its scan.
 *
 * These replaced the `/monitoring/overview`, `/health`, `/feedback`,
 * `/subsections` and `/scan/{subsection}` reads. The URLs changed because
 * the source did: the figures now arrive through the MCP tool registry
 * rather than from the store directly, so they are redacted, scoped to a
 * subsection and recorded in the tool-call audit.
 */
export const mcpApi = {
  subsections: () =>
    request<{
      subsections: MonitoringSubsection[];
      scan_enabled: boolean;
      scan_llm_enabled: boolean;
    }>('/api/mcp/panel/subsections'),

  /** Everything the panels need, one round trip, one consistent window. */
  overview: (days = 7, platform: string | null = null) => {
    const search = new URLSearchParams({ days: String(days) });
    if (platform) search.set('platform', platform);
    return request<unknown>(`/api/mcp/panel/overview?${search}`);
  },

  health: (days = 7, platform = 'web') =>
    request<unknown>(`/api/mcp/panel/health?days=${days}&platform=${platform}`),

  /** Subsection D: volume, sentiment and topic mix. Read-only. */
  feedback: (days = 30) => request<unknown>(`/api/mcp/panel/feedback?days=${days}`),

  /**
   * Run a scan for one subsection.
   *
   * The scan is model-driven end to end: the subsection's tools answer, the
   * model writes the verdict, and every number it cited is reconciled
   * against the audit trail. It reaches a hosted model, so it is not
   * instant - the UI shows a pending state rather than appearing to have
   * hung.
   */
  scan: (subsection: string, windowDays = 7) =>
    request<ScanResultResponse>(`/api/mcp/scan/${subsection}`, {
      method: 'POST',
      body: { window_days: windowDays },
    }),
};

export const monitoringApi = {
  /**
   * Every scan verdict, the incident log and the tool-call audit.
   *
   * Still here rather than in the MCP layer: it is the record of what the
   * scans concluded, and MCP records what the tools answered - two different
   * things, and the console shows both.
   */
  history: (subsection: string | null = null, limit = 50) => {
    const search = new URLSearchParams({ limit: String(limit) });
    if (subsection) search.set('subsection', subsection);
    return request<unknown>(`/monitoring/history?${search}`);
  },

  /** Rebuild the hourly rollup now, instead of waiting for the timer. */
  rollup: (lookbackHours = 48) =>
    request<{ rows_written: number; events_scanned: number }>(
      `/monitoring/rollup?lookback_hours=${lookbackHours}`,
      { method: 'POST' }
    ),
};

// ------------------------------------------------------------ oppfeed
//
// OppFeed integration: admin-managed opportunity discovery + faculty-facing
// feed. All endpoints live under /admin/oppfeed/* (admin) or
// /faculty/oppfeed/* (faculty). Auth is CampusPilot JWT — same cookie,
// same get_token().

/** Admin: List opportunities (paginated, filterable). */
export const oppfeedApi = {
  // ---- Faculty feed ----
  listFaculty: (params: OpportunityFilterParams = {}) => {
    const search = new URLSearchParams();
    if (params.page) search.set('page', String(params.page));
    if (params.page_size) search.set('page_size', String(params.page_size));
    if (params.status) search.set('status', params.status);
    if (params.opportunity_type) search.set('opportunity_type', params.opportunity_type);
    if (params.search) search.set('search', params.search);
    if (params.source_domain) search.set('source_domain', params.source_domain);
    if (params.date_from) search.set('date_from', params.date_from);
    if (params.date_to) search.set('date_to', params.date_to);
    return request<PaginatedOpportunities>(`/faculty/oppfeed?${search}`);
  },
  facultyFilters: () => request<FeedFilters>('/faculty/oppfeed/filters'),
  facultyDetail: (slug: string) =>
    request<OpportunityDetail>(`/faculty/oppfeed/${encodeURIComponent(slug)}`),

  // ---- Admin: Opportunities ----
  listOpportunities: (params: OpportunityFilterParams = {}) => {
    const search = new URLSearchParams();
    if (params.page) search.set('page', String(params.page));
    if (params.page_size) search.set('page_size', String(params.page_size));
    if (params.status) search.set('status', params.status);
    if (params.opportunity_type) search.set('opportunity_type', params.opportunity_type);
    if (params.search) search.set('search', params.search);
    if (params.source_domain) search.set('source_domain', params.source_domain);
    if (params.date_from) search.set('date_from', params.date_from);
    if (params.date_to) search.set('date_to', params.date_to);
    return request<OpportunityListItem[]>(`/admin/oppfeed/opportunities?${search}`);
  },
  getOpportunity: (id: number) =>
    request<OpportunityDetailAdmin>(`/admin/oppfeed/opportunities/${id}`),
  updateOpportunity: (id: number, data: OpportunityUpdateRequest) =>
    request<OpportunityDetailAdmin>(`/admin/oppfeed/opportunities/${id}`, {
      method: 'PATCH',
      body: data,
    }),
  bulkAction: (data: BulkActionRequest) =>
    request<{ processed: number; action: string }>('/admin/oppfeed/opportunities/bulk', {
      method: 'POST',
      body: data,
    }),
  transitionState: (id: number, data: StateTransitionRequest) =>
    request<OpportunityDetailAdmin>(`/admin/oppfeed/opportunities/${id}/transition`, {
      method: 'POST',
      body: data,
    }),

  // ---- Admin: Agent runs ----
  listRuns: (
    params: { page?: number; page_size?: number; status?: string; mode?: string } = {}
  ) => {
    const search = new URLSearchParams();
    if (params.page) search.set('page', String(params.page));
    if (params.page_size) search.set('page_size', String(params.page_size));
    if (params.status) search.set('status', params.status);
    if (params.mode) search.set('mode', params.mode);
    return request<RunListItem[]>(`/admin/oppfeed/runs?${search}`);
  },
  createRun: (data: RunCreateRequest) =>
    request<RunResponse>(`/admin/oppfeed/runs`, { method: 'POST', body: data }),
  getRun: (runId: string) =>
    request<RunResponse>(`/admin/oppfeed/runs/${encodeURIComponent(runId)}`),

  // ---- Admin: Agent settings ----
  getSettings: () => request<AgentSettingsResponse>('/admin/oppfeed/settings'),
  updateSettings: (data: AgentSettingsUpdateRequest) =>
    request<AgentSettingsResponse>('/admin/oppfeed/settings', { method: 'PATCH', body: data }),

  // ---- Admin: Source rules ----
  listSourceRules: () => request<SourceRuleResponse[]>('/admin/oppfeed/source-rules'),
  createSourceRule: (data: SourceRuleCreateRequest) =>
    request<SourceRuleResponse>('/admin/oppfeed/source-rules', { method: 'POST', body: data }),
  updateSourceRule: (id: number, data: SourceRuleUpdateRequest) =>
    request<SourceRuleResponse>(`/admin/oppfeed/source-rules/${id}`, {
      method: 'PATCH',
      body: data,
    }),
  deleteSourceRule: (id: number) =>
    request<void>(`/admin/oppfeed/source-rules/${id}`, { method: 'DELETE' }),

  // ---- Admin: Search queries ----
  listSearchQueries: () => request<SearchQueryResponse[]>('/admin/oppfeed/search-queries'),
  createSearchQuery: (data: SearchQueryCreateRequest) =>
    request<SearchQueryResponse>('/admin/oppfeed/search-queries', {
      method: 'POST',
      body: data,
    }),
  updateSearchQuery: (id: number, data: SearchQueryUpdateRequest) =>
    request<SearchQueryResponse>(`/admin/oppfeed/search-queries/${id}`, {
      method: 'PATCH',
      body: data,
    }),
  deleteSearchQuery: (id: number) =>
    request<void>(`/admin/oppfeed/search-queries/${id}`, { method: 'DELETE' }),

  // ---- Admin: LLM status ----
  llmStatus: () => request<LLMStatusResponse>('/admin/oppfeed/llm-status'),
  testLLM: (data: LLMTestRequest) =>
    request<LLMTestResponse>('/admin/oppfeed/llm-test', { method: 'POST', body: data }),

  // ---- Admin: Feedback ----
  listFeedback: (opportunityId: number) =>
    request<OppFeedFeedbackResponse[]>(`/admin/oppfeed/opportunities/${opportunityId}/feedback`),
  createFeedback: (opportunityId: number, data: OppFeedFeedbackCreateRequest) =>
    request<OppFeedFeedbackResponse>(`/admin/oppfeed/opportunities/${opportunityId}/feedback`, {
      method: 'POST',
      body: data,
    }),
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
