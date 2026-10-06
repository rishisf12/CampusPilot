/** Shared, non-component data so Fast Refresh stays happy. */

/** Branch dropdown. No bare "CSE" and no duplicates. "DS" is the BDes branch. */
export const BRANCH_OPTIONS = ['CSE A', 'CSE B', 'DS', 'ECE', 'ME', 'SM', 'PG', 'MDes']

export const PROGRAMMES = ['BTech', 'BDes', 'MTech', 'MDes', 'PhD']

export const GENDERS = ['Male', 'Female', 'Other']

/**
 * How long the "Resend Code" button stays disabled after a signup or a resend.
 *
 * Shared rather than repeated: AuthWrapper starts the clock when a signup
 * completes, and VerifyEmail counts it down, so the two have to agree.
 */
export const RESEND_COOLDOWN_SECONDS = 60

/** Semester choices per programme. */
export const PROGRAMME_SEMESTERS = {
  BTech: [1, 2, 3, 4, 5, 6, 7, 8],
  BDes: [1, 2, 3, 4, 5, 6, 7, 8],
  MTech: [1, 2, 3, 4],
  MDes: [1, 2, 3, 4],
  PhD: [1, 2],
}

const ROMAN = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII' }

/** `5` -> `"V Sem"`. */
export function semesterLabel(value) {
  return `${ROMAN[value] || value} Sem`
}

export const ALLOWED_EMAIL_DOMAIN = '@iiitdmj.ac.in'

/** Top-level navigation tabs rendered inside the single header. */
export const NAV_TABS = [
  { id: 'live', label: 'Live Schedule' },
  { id: 'vacant', label: 'Vacant Room Lookup' },
  { id: 'attendance', label: 'Attendance' },
  { id: 'exam', label: 'Exam' },
]

/** My Team sub-tabs: discover, own teams, incoming requests, hackathon feed. */
export const TEAM_TABS = [
  { id: 'discover', label: 'Discover' },
  { id: 'mine', label: 'My Teams' },
  { id: 'requests', label: 'Requests' },
  { id: 'feed', label: 'Feed' },
]

/** Skill tags offered when creating a team or editing team-profile skills. */
export const SKILL_OPTIONS = [
  'python', 'react', 'nodejs', 'fastapi', 'sql', 'postgres', 'docker',
  'ml', 'tensorflow', 'pandas', 'flutter', 'tailwindcss', 'figma',
]

/**
 * Match-score tone. Thresholds are shared by the card badge and the bar so a
 * score never reads as green in one place and amber in another.
 */
export function toneFor(score) {
  if (score >= 75) return 'success'
  if (score >= 40) return 'warning'
  return 'danger'
}

/** Open / Full / Pending pill, matching the attendance SAFE badge pattern. */
export function teamStatus(team, pending) {
  if (pending) return { label: 'PENDING', tone: 'warning' }
  if (!team.is_open) return { label: 'CLOSED', tone: 'danger' }
  if (team.members_count >= team.max_members) return { label: 'FULL', tone: 'danger' }
  return { label: 'OPEN', tone: 'success' }
}

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']