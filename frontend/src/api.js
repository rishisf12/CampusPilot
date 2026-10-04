/**
 * API client.
 *
 * Every request goes through the Vite proxy to the FastAPI backend on port 8001
 * and carries the stored JWT.  A 401 is the *only* thing that clears the
 * session: network failures must not sign the user out.
 */

const API_BASE = ''

const TOKEN_KEY = 'auth_token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable (private mode) - the session simply won't persist */
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('pending_verification_email')
  } catch {
    /* ignore */
  }
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
    throw new ApiError(Array.isArray(detail) ? detail.join(', ') : detail, response.status)
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
}

// --------------------------------------------------------------- exam
export const examApi = {
  status: () => request('/exam/status'),
  uploadTimetable: (file) => upload('/exam/timetable/upload', file),
  uploadSeating: (file) => upload('/exam/seating/upload', file),
  getTimetable: () => request('/exam/timetable'),
  getSeating: () => request('/exam/seating'),
  lookup: (roll) => request(`/exam/lookup?roll=${encodeURIComponent(roll)}`),
  clearTimetable: () => request('/exam/timetable', { method: 'DELETE' }),
  clearSeating: () => request('/exam/seating', { method: 'DELETE' }),
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

// ------------------------------------------------------------- health
export const healthApi = {
  check: () => request('/health'),
}

/**
 * Monotonic key the Exam page watches to refetch after profile edits.
 * A same-tab event is dispatched too, since `storage` only fires elsewhere.
 */
export function bumpProfileVersion() {
  let next = '1'
  try {
    next = String(Number(localStorage.getItem('profile_version') || 0) + 1)
    localStorage.setItem('profile_version', next)
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent('profile-updated', { detail: { version: next } }))
}