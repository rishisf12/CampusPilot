/** Shared frontend constants, kept out of component files for Fast Refresh. */

/** The eight branches offered in every dropdown. */
export const BRANCH_OPTIONS = ['CSE A', 'CSE B', 'DS', 'ECE', 'ME', 'SM', 'PG', 'MDes']

/** Programmes a student can register under. */
export const PROGRAMMES = ['BTech', 'BDes', 'MTech', 'MDes', 'PhD']

/** Semester choices available per programme. */
export const PROGRAMME_SEMESTERS = {
  BTech: [1, 2, 3, 4, 5, 6, 7, 8],
  BDes: [1, 2, 3, 4, 5, 6, 7, 8],
  MTech: [1, 2, 3, 4],
  MDes: [1, 2, 3, 4],
  PhD: ['Coursework'],
}

const ROMAN = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII' }

/** `5` -> `"V Sem"`, `"Coursework"` -> `"Coursework"`. */
export function semesterLabel(value) {
  return value === 'Coursework' ? 'Coursework' : `${ROMAN[value] || value} Sem`
}