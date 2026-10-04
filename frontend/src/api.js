/**
 * API client for CampusPilot.
 *
 * The JWT is stored in localStorage and attached to every request; a 401 clears
 * it so the app falls back to the login screen.
 */
const API_BASE = import.meta.env.VITE_API_URL || ''

const TOKEN_KEY = 'campuspilot_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request(path, options = {}) {
  const headers = { ...options.headers }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  // FormData and URLSearchParams must keep their own content type so the
  // browser sets multipart/form-data or application/x-www-form-urlencoded.
  const body = options.body
  const isRawBody = body instanceof FormData || body instanceof URLSearchParams
  if (body && !isRawBody) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (res.status === 401 && !path.startsWith('/auth/login')) {
    setToken(null)
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

async function upload(path, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await request(path, { method: 'POST', body: form })
  if (res && res.detail) throw new Error(res.detail)
  return res
}

// Health
export const healthApi = {
  check: () => request('/health'),
}

// Auth
export const authApi = {
  signup: (data) => request('/auth/signup', { method: 'POST', body: JSON.stringify(data) }),
  verifyEmail: (email, code) =>
    request('/auth/verify-email', { method: 'POST', body: JSON.stringify({ email, code }) }),
  resendCode: (email) =>
    request('/auth/resend-code', { method: 'POST', body: JSON.stringify({ email }) }),
  // The backend login is an OAuth2 password form, not JSON.
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      body: new URLSearchParams({ username, password }),
    }),
  me: () => request('/auth/me'),
  logout: () => request('/auth/logout', { method: 'POST' }),
}

// Profile
export const profileApi = {
  get: () => request('/profile/'),
  update: (data) => request('/profile/', { method: 'PUT', body: JSON.stringify(data) }),
  options: () => request('/profile/options'),
  requestBranchChange: (data) =>
    request('/profile/branch-change', { method: 'POST', body: JSON.stringify(data) }),
  clearBranchChange: () => request('/profile/branch-change', { method: 'DELETE' }),
}

// Exam
export const examApi = {
  status: () => request('/exam/status'),
  uploadSeating: (file) => upload('/exam/seating/upload', file),
  uploadTimetable: (file) => upload('/exam/timetable/upload', file),
  timetable: () => request('/exam/timetable'),
  seating: () => request('/exam/seating'),
  lookup: (roll) => request(`/exam/lookup?roll=${encodeURIComponent(roll)}`),
  quickLookup: (roll) => request(`/exam/quick-lookup?roll=${encodeURIComponent(roll)}`),
  pdfUrl: (roll) => `${API_BASE}/exam/pdf?roll=${encodeURIComponent(roll)}`,
  pdf: async (roll) => {
    const res = await fetch(`${API_BASE}/exam/pdf?roll=${encodeURIComponent(roll)}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) throw new Error('Could not generate the exam PDF')
    return res.blob()
  },
}

// Timetable
export const timetableApi = {
  upload: (file) => upload('/timetable/upload', file),
  options: () => request('/timetable/options'),
  clear: () => request('/timetable', { method: 'DELETE' }),
  listSlots: () => request('/timetable/slots'),
}

// Attendance
export const attendanceApi = {
  subjects: () => request('/attendance/subjects'),
  summary: () => request('/attendance/summary'),
  course: (id) => request(`/attendance/course/${id}`),
  mark: (data) => request('/attendance/', { method: 'POST', body: JSON.stringify(data) }),
  records: (courseId) =>
    request(`/attendance/records${courseId ? `?course_id=${courseId}` : ''}`),
  delete: (id) => request(`/attendance/${id}`, { method: 'DELETE' }),
  sync: () => request('/attendance/sync'),
}

// Rooms
export const roomsApi = {
  vacant: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/rooms/vacant${query ? `?${query}` : ''}`)
  },
  all: () => request('/rooms/all'),
}

// Schedule
export const scheduleApi = {
  now: () => request('/schedule/now'),
  listExtra: () => request('/schedule/courses/extra'),
  addExtra: (data) =>
    request('/schedule/courses/extra', { method: 'POST', body: JSON.stringify(data) }),
  removeExtra: (code) =>
    request(`/schedule/courses/extra/${encodeURIComponent(code)}`, { method: 'DELETE' }),
}