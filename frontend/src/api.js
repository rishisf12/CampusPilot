const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Attendance
export const attendanceApi = {
  mark: (data) => request('/attendance', { method: 'POST', body: JSON.stringify(data) }),
  summary: () => request('/attendance/summary'),
  course: (id) => request(`/attendance/course/${id}`),
  delete: (id) => request(`/attendance/${id}`, { method: 'DELETE' }),
}

// Timetable
export const timetableApi = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${API_BASE}/timetable/upload`, { method: 'POST', body: form }).then(r => r.json())
  },
  debug: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${API_BASE}/timetable/debug/parse-timetable`, { method: 'POST', body: form }).then(r => r.json())
  },
  clear: () => request('/timetable', { method: 'DELETE' }),
  editSlot: (id, data) => request(`/timetable/slot/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  listSlots: () => request('/timetable/slots'),
}

// Profile
export const profileApi = {
  get: () => request('/profile'),
  update: (data) => request('/profile', { method: 'PUT', body: JSON.stringify(data) }),
}

// Schedule
export const scheduleApi = {
  now: () => request('/schedule/now'),
  addExtra: (data) => request('/schedule/courses/extra', { method: 'POST', body: JSON.stringify(data) }),
  listExtra: () => request('/schedule/courses/extra'),
  removeExtra: (code) => request(`/schedule/courses/extra/${code}`, { method: 'DELETE' }),
}

// Rooms
export const roomsApi = {
  vacant: (params) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/rooms/vacant?${qs}`)
  },
  all: () => request('/rooms/all'),
}

// Exam
export const examApi = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${API_BASE}/exam/upload`, { method: 'POST', body: form }).then(r => r.json())
  },
  debug: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${API_BASE}/exam/debug/parse-exam`, { method: 'POST', body: form }).then(r => r.json())
  },
  lookup: (roll) => request(`/exam/lookup?roll=${encodeURIComponent(roll)}`),
  pdf: (roll) => fetch(`${API_BASE}/exam/pdf?roll=${encodeURIComponent(roll)}`).then(r => r.blob()),
}

// Health
export const healthApi = {
  check: () => request('/health'),
}