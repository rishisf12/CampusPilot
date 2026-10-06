/**
 * API client.
 *
 * Every request goes through the Vite proxy to the FastAPI backend on port 8001
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
} from './lib/storage'

const API_BASE = ''

export {
  clearSession,
  getToken,
  setToken,
  getProfileVersion,
  bumpProfileVersion,
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** True when the session should be dropped. */
export function isUnauthorized(error) {
  return error instanceof ApiError && error.status === 401
}

/**
 * Turn an error body into one readable line.
 *
 * FastAPI answers a validation failure (422) with `detail` as a *list of
 * objects*, so joining it directly would render `[object Object]`. Each entry's
 * `msg` is the useful part; fall back to JSON for anything unrecognised.
 */
function formatDetail(detail) {
  if (!Array.isArray(detail)) return detail
  const parts = detail.map((item) => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') return item.msg || JSON.stringify(item)
    return String(item)
  })
  return parts.join(', ') || 'Request failed'
}

async function request(path, options = {}) {
  const { body, headers: optionHeaders, ...rest } = options
  const headers = { ...optionHeaders }

  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let payload = body
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData
  const isUrlEncoded = typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams
  if (body && !isForm && !isUrlEncoded) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...rest, headers, body: payload })
  } catch {
    throw new ApiError('Backend offline', 0)
  }

  if (response.status === 204) return null

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    const detail =
      (data && typeof data === 'object' && (data.detail || data.message)) ||
      (typeof data === 'string' && data) ||
      `Request failed (${response.status})`
    throw new ApiError(formatDetail(detail), response.status)
  }

  return data
}

function upload(path, file, extra = {}) {
  const form = new FormData()
  form.append('file', file)
  return request(path, { method: 'POST', body: form, ...extra })
}

// ---------------------------------------------------------------- auth
export const authApi = {
  /**
   * Step 1 of registration: ask for a code, without creating anything yet.
   *
   * Always returns the same message whether or not the address is eligible, so
   * this cannot be used to find out who has an account here.
   */
  startSignup: (email) =>
    request('/auth/signup/start', { method: 'POST', body: { email } }),
  /** Step 2: confirm the code. This is what makes the address usable. */
  verifySignup: (email, code) =>
    request('/auth/signup/verify', { method: 'POST', body: { email, code } }),
  /** Step 3: create the account. Refused unless step 2 has been done. */
  signup: (data) => request('/auth/signup', { method: 'POST', body: data }),
  verifyEmail: (data) => request('/auth/verify-email', { method: 'POST', body: data }),
  // The backend exposes this as /auth/resend-code and expects an object body.
  resendVerificationCode: (data) => request('/auth/resend-code', { method: 'POST', body: data }),
  login: (username, password) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return request('/auth/login', { method: 'POST', body: form })
  },
  me: () => request('/auth/me'),
  logout: () => request('/auth/logout', { method: 'POST' }),
  /**
   * Ask for a password reset code.
   *
   * The response is the same whether or not the account exists, so this returns a
   * message and nothing else - there is deliberately no `sent: true/false` flag
   * to branch on.
   */
  forgotPassword: (identifier) =>
    request('/auth/forgot-password', { method: 'POST', body: { identifier } }),
  /** Set a new password from an emailed code. */
  resetPassword: (identifier, code, newPassword) =>
    request('/auth/reset-password', {
      method: 'POST',
      body: { identifier, code, new_password: newPassword },
    }),
  /**
   * The signed-in user's passkeys.
   *
   * Used to decide whether to offer enrolment after a first sign-in. The actual
   * WebAuthn exchange lives in `lib/passkey.js`, which talks to the browser API
   * directly - it cannot go through `request` because the credential bytes must
   * not be stringified on the way out.
   */
  passkeys: () => request('/auth/passkeys'),
  /**
   * Revoke a passkey, e.g. after losing the device that held it.
   *
   * The credential id is base64url, which contains characters a path segment
   * allows but that still need encoding to be safe in a URL.
   */
  removePasskey: (credentialId) =>
    request(`/auth/passkeys/${encodeURIComponent(credentialId)}`, { method: 'DELETE' }),
}

// ------------------------------------------------------------- profile
export const profileApi = {
  get: () => request('/profile/'),
  update: (data) => request('/profile/', { method: 'PUT', body: data }),
  options: () => request('/profile/options'),
  requestBranchChange: (data) => request('/profile/branch-change', { method: 'POST', body: data }),
  clearBranchChange: () => request('/profile/branch-change', { method: 'DELETE' }),
}

// ------------------------------------------------------------ schedule
export const scheduleApi = {
  now: () => request('/schedule/now'),
  listExtra: () => request('/schedule/courses/extra'),
  addExtra: (data) => request('/schedule/courses/extra', { method: 'POST', body: data }),
  removeExtra: (code) => request(`/schedule/courses/extra/${encodeURIComponent(code)}`, { method: 'DELETE' }),
}

// ----------------------------------------------------------- timetable
export const timetableApi = {
  upload: (file) => upload('/timetable/upload', file),
  options: () => request('/timetable/options'),
  listSlots: () => request('/timetable/slots'),
  clear: () => request('/timetable/', { method: 'DELETE' }),
  /** Metadata for the newest uploaded timetable, or `{ available: false }`. */
  latestUpload: () => request('/timetable/uploads/latest'),
  /**
   * Object URL for the newest uploaded timetable, or `null` when there is none.
   *
   * The preview endpoint is authenticated, so it is fetched with the bearer token
   * and handed over as a blob: a plain link would go out without the
   * `Authorization` header and come back 401. The caller owns the returned URL
   * and must `URL.revokeObjectURL` it.
   */
  previewObjectUrl: async () => {
    const token = getToken()
    if (!token) return null
    const response = await fetch('/timetable/uploads/preview', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Could not load the preview')
    return URL.createObjectURL(await response.blob())
  },
}

// --------------------------------------------------------------- exam
export const examApi = {
  status: () => request('/exam/status'),
  uploadTimetable: (file) => upload('/exam/timetable/upload', file),
  uploadSeating: (file) => upload('/exam/seating/upload', file),
  getTimetable: () => request('/exam/timetable'),
  getSeating: () => request('/exam/seating'),
  lookup: (roll) => request(`/exam/lookup?roll=${encodeURIComponent(roll)}`),
  clashes: (roll) =>
    request(`/exam/clashes${roll ? `?roll=${encodeURIComponent(roll)}` : ''}`),
  clearTimetable: () => request('/exam/timetable', { method: 'DELETE' }),
  clearSeating: () => request('/exam/seating', { method: 'DELETE' }),
  /** Metadata for the newest file uploaded to a section, or `{ available: false }`. */
  latestUpload: (kind) => request(`/exam/uploads/latest?kind=${encodeURIComponent(kind)}`),
  /**
   * Object URL for the newest uploaded file, or `null` when there is none.
   *
   * The preview endpoint is authenticated, so it is fetched with the bearer token
   * and handed over as a blob: a plain link or `window.open` would go out without
   * the `Authorization` header and come back 401. The caller owns the returned
   * URL and must `URL.revokeObjectURL` it.
   */
  previewObjectUrl: async (kind) => {
    const token = getToken()
    if (!token) return null
    const response = await fetch(`/exam/uploads/preview?kind=${encodeURIComponent(kind)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Could not load the preview')
    return URL.createObjectURL(await response.blob())
  },
}

// -------------------------------------------------------------- rooms
export const roomsApi = {
  vacant: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''),
    ).toString()
    return request(`/rooms/vacant${query ? `?${query}` : ''}`)
  },
  all: () => request('/rooms/all'),
}

// -------------------------------------------------------------- teams
function teamQuery(params) {
  const search = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.append(key, value)
  })
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

export const teamsApi = {
  list: (params) => request(`/teams${teamQuery(params)}`),
  matches: (params) => request(`/teams/match${teamQuery(params)}`),
  mine: () => request('/teams/mine'),
  requests: () => request('/teams/requests'),
  get: (id) => request(`/teams/${id}`),
  create: (data) => request('/teams', { method: 'POST', body: data }),
  update: (id, data) => request(`/teams/${id}`, { method: 'PUT', body: data }),
  remove: (id) => request(`/teams/${id}`, { method: 'DELETE' }),
  join: (id) => request(`/teams/${id}/join`, { method: 'POST' }),
  leave: (id) => request(`/teams/${id}/leave`, { method: 'POST' }),
  respond: (requestId, status) =>
    request(`/teams/requests/${requestId}`, { method: 'PUT', body: { status } }),
}

// ---------------------------------------------------------- hackathons
export const hackathonsApi = {
  list: (params) => request(`/hackathons${teamQuery(params)}`),
  create: (data) => request('/hackathons', { method: 'POST', body: data }),
  /** Pull new mail and sweep anything past the retention window. */
  sync: () => request('/hackathons/feed/sync', { method: 'POST' }),
}

// ---------------------------------------------------------- attendance
// The backend serves subjects/summary/records/course and the sync trigger.
// The banner, history, per-subject "today" state, calendar and attendance
// target are derived on the client from these.
export const attendanceApi = {
  summary: () => request('/attendance/summary'),
  subjects: () => request('/attendance/subjects'),
  records: (courseId) =>
    request(`/attendance/records${courseId ? `?course_id=${courseId}` : ''}`),
  course: (id) => request(`/attendance/course/${id}`),
  mark: (data) => request('/attendance/', { method: 'POST', body: data }),
  remove: (id) => request(`/attendance/${id}`, { method: 'DELETE' }),
  sync: () => request('/attendance/sync'),
}

// ---------------------------------------------------------- feedback
export const feedbackApi = {
  /**
   * Submit feedback text with an optional file.
   *
   * Sent as multipart FormData so the attachment rides along with the fields.
   * Name/phone/email fall back to the profile on the server, so only the
   * message is required here.
   */
  submit: ({ message, name, phone, email, file }) => {
    const form = new FormData()
    form.append('message', message)
    if (name) form.append('name', name)
    if (phone) form.append('phone', phone)
    if (email) form.append('email', email)
    if (file) form.append('file', file)
    return request('/feedback/', { method: 'POST', body: form })
  },
  /** The signed-in student's own submissions, newest first. */
  mine: () => request('/feedback/mine'),
  /** Every response, newest first. Admin-only; backs the admin responses view. */
  responses: () => request('/feedback/responses'),
  /** Answer one feedback as admin. Appears under the student's entry. */
  reply: (id, message) =>
    request(`/feedback/${id}/reply`, { method: 'POST', body: { message } }),
}

// ------------------------------------------------------------- health
export const healthApi = {
  check: () => request('/health'),
}