/** Shared, non-component data so Fast Refresh stays happy. */

/** Branch dropdown. No bare "CSE" and no duplicates. "DS" is the BDes branch. */
export const BRANCH_OPTIONS = ['CSE A', 'CSE B', 'DS', 'ECE', 'ME', 'SM', 'PG', 'MDes']

export const PROGRAMMES = ['BTech', 'BDes', 'MTech', 'MDes', 'PhD']

export const GENDERS = ['Male', 'Female', 'Other']

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

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']