/**
 * Shared normalisation for branch and room names.
 *
 * The same real-world value reaches the frontend in several shapes - "CSE A",
 * "CSE-A", "cse a", "B.Tech CSE", "BDes DS". Comparing those as raw strings
 * produces duplicate rows and false mismatches, so everything is folded to a
 * canonical form first. Timetable rows, exam rows and room lists all go through
 * here, which is what keeps one class from appearing twice after a sync.
 */

/** Branch prefixes used in roll numbers and course codes. */
const BRANCH_FAMILY: Record<string, string> = {
  CSE: 'CSE',
  DS: 'DS',
  IT: 'ECE',
  ECE: 'ECE',
  EL: 'ECE',
  ME: 'ME',
  SM: 'SM',
  PG: 'PG',
  MDES: 'MDES',
};

/** Course code prefix -> branch family mapping. */
const COURSE_PREFIX_BRANCH: Record<string, string> = {
  CS: 'CSE',
  EC: 'ECE',
  ME: 'ME',
  SM: 'SM',
  DS: 'DS',
  IT: 'ECE',
  HS: 'CSE', // Humanities - generic
  NS: 'CSE', // Natural Sciences - generic
  MT: 'CSE', // Math - generic
  ES: 'CSE', // Engineering Science - generic
  OE: 'CSE', // Open Elective - generic
  NM: 'PG', // PhD/Research
  EC5: 'ECE', // ECE postgrad
  ME5: 'ME', // ME postgrad
  SM5: 'SM', // SM postgrad
  DS5: 'DS', // DS postgrad
  CS8: 'CSE', // CSE postgrad
};

/** Prefixes that indicate postgraduate (MTech/ME) courses. */
const POSTGRAD_PREFIXES = new Set([
  'EC5',
  'ME5',
  'SM5',
  'DS5',
  'CS8',
  'ME6',
  'EC6',
  'SM6',
  'DS6',
  'CS9',
  'ME8',
  'EC8',
  'SM8',
  'DS8',
]);

/** Check if a course code indicates a postgraduate (MTech/ME) course. */
export function isPostgradCourse(code: string): boolean {
  if (!code) return false;
  const match = code.match(/^([A-Z]+[5689]?)/);
  if (!match) return false;
  const prefix = match[1].toUpperCase();
  return POSTGRAD_PREFIXES.has(prefix);
}

/** The canonical branch list, used as the fallback for unrecognised input. */
export const BRANCHES = ['CSE A', 'CSE B', 'DS', 'ECE', 'ME', 'SM', 'PG', 'MDes'];

/**
 * Reduce a branch label to its family: "CSE A" and "CSE-B" both become "CSE".
 *
 * `DS` stays `DS` because it is a branch in its own right, not a section of
 * another one - and BDes students must not be folded into anything else.
 *
 * Postgraduate programmes are degrees, not departments, so they are matched
 * first and against a punctuation-free copy: the timetable writes "M.Tech",
 * "Ph.D." and "MDes (Sem I)" dotted and spaced. Left to the department prefixes
 * below, "M.Tech (Mechatronics)" reads as ME and "M.Tech (Design)" as MDes -
 * and a dotted "M.TECH" never matched "MTECH" at all.
 */
export function branchFamily(value: string | undefined | null): string {
  if (!value) return '';
  const compact = String(value)
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
  if (!compact) return '';
  if (compact.includes('PHD') || compact.includes('DOCTOR')) return 'PG';
  if (compact.includes('MTECH')) return 'PG';
  // Bachelor of Design is an undergraduate branch, not the master's one.
  if (compact.includes('BDES')) return 'DS';
  if (compact.includes('MDES') || compact.includes('DESIGN')) return 'MDES';
  const cleaned = compact.replace(/BTECH|SEMESTER|SEM/g, '');
  if (!cleaned) return '';
  // Longest prefix first so "MDES" is not read as "ME".
  for (const prefix of Object.keys(BRANCH_FAMILY).sort((a, b) => b.length - a.length)) {
    if (cleaned.startsWith(prefix)) return BRANCH_FAMILY[prefix];
  }
  return cleaned;
}

/** Separators used between branches in a shared timetable cell ("ECE ME SM"). */
const BRANCH_TOKEN_SEP = /[\s,;/&+]+/;

/**
 * Every branch family named anywhere in a free-text cell.
 *
 * A cell may hold one branch ("MDS501" -> ["MDES"]), several shared ones
 * ("ECE ME SM" -> ["ECE", "ME", "SM"]) or a postgraduate label
 * ("M.Tech (P&C)" -> ["PG"]). Comparing memberships rather than the first match
 * means a shared row reaches every branch it belongs to.
 */
export function branchesInText(value: string | undefined | null): string[] {
  if (!value) return [];
  const families = new Set<string>();
  const whole = branchFamily(value);
  if (whole) families.add(whole);
  String(value)
    .split(BRANCH_TOKEN_SEP)
    .forEach(token => {
      const family = branchFamily(token);
      if (family) families.add(family);
    });
  return [...families];
}

/**
 * True when two branch labels refer to the same branch family.
 *
 * Used where a section split should still count as a match - a CSE A student
 * genuinely sits the papers listed under CSE B - while a plain "CSE" in the
 * source never creates a second, duplicate row.
 */
export function sameBranchFamily(
  a: string | undefined | null,
  b: string | undefined | null
): boolean {
  const left = branchFamily(a);
  const right = branchFamily(b);
  if (!left || !right) return false;
  return left === right;
}

/**
 * Extract branch family from a course code prefix.
 * e.g., "ME3010L" -> "ME", "EC3011" -> "ECE", "SM3012" -> "SM"
 */
export function branchFromCourseCode(code: string): string {
  if (!code) return '';
  // Extract prefix: letters before first digit (or digit sequence)
  const match = code.match(/^([A-Z]+)/);
  if (!match) return '';
  const prefix = match[1];
  // Try exact match first
  if (COURSE_PREFIX_BRANCH[prefix]) return COURSE_PREFIX_BRANCH[prefix];
  // Fallback: use BRANCH_FAMILY if prefix matches a known branch
  if (BRANCH_FAMILY[prefix]) return BRANCH_FAMILY[prefix];
  return '';
}

/**
 * Check if a slot's course code belongs to the student's branch.
 * For shared cells (multiple branches in branch_or_program), only allow
 * courses whose code prefix matches the student's branch.
 */
export function courseBelongsToBranch(courseCode: string, studentBranch: string): boolean {
  const studentFamily = branchFamily(studentBranch);
  if (!studentFamily) return false;
  const courseFamily = branchFromCourseCode(courseCode);
  return courseFamily === studentFamily;
}

/**
 * Normalise a room name: uppercase, one dash between letters and digits.
 *
 * "CR 201", "cr-201" and "CR201" are the same room; without this they would
 * each occupy their own slot in the occupied/vacant lists.
 */
export function normaliseRoom(value: string | undefined | null): string {
  if (!value) return '';
  let room = String(value).trim().toUpperCase().replace(/\s+/g, '');
  // Insert a single dash between the letter group and the number.
  room = room.replace(/^([A-Z]+)[\s-]*(\d+)$/, '$1-$2');
  return room;
}

interface TimetableSlot {
  day?: string;
  start_time?: string;
  end_time?: string;
  room?: string;
  course_code?: string;
}

/**
 * A stable key for one class, used to drop duplicates after a sync.
 *
 * A class is identified by when and where it happens, not by its row id: the
 * same class can arrive twice from a re-uploaded timetable, or from two
 * sections sharing a room.
 */
export function classKey(item: TimetableSlot | undefined | null): string {
  return [
    item?.day || '',
    item?.start_time || '',
    item?.end_time || '',
    normaliseRoom(item?.room),
    (item?.course_code || '').trim().toUpperCase(),
  ].join('|');
}

/** Drop repeated classes, keeping the first occurrence. */
export function dedupeClasses<T extends TimetableSlot>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter(item => {
    const key = classKey(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** Drop repeated rooms, keeping the first occurrence. */
export function dedupeRooms(rooms: Array<string | undefined | null>): string[] {
  const seen = new Set<string>();
  return rooms.filter((room): room is string => {
    const key = normaliseRoom(room);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Split a course-code cell that lists two papers, e.g. "OE3M27/ME5D02".
 *
 * Timetables pack paired papers into one cell; treating that as a single course
 * hides one of them from the student's attendance and exam lists.
 */
export function splitCourseCodes(value: string | undefined | null): string[] {
  if (!value) return [];
  return String(value)
    .split(/[/|,]/)
    .map(code => code.trim().toUpperCase())
    .filter(Boolean);
}

/** An open elective, which every branch may take. */
export function isOpenElective(code: string | undefined | null): boolean {
  return /^(OE|OI)\d/i.test(String(code || '').trim());
}

interface TimetableSlotWithInstructor extends TimetableSlot {
  instructor?: string;
}

/**
 * Who teaches a course, according to the uploaded timetable.
 *
 * The attendance and exam APIs return no instructor - the field only exists on a
 * timetable slot - so those screens would otherwise show a bare course code. The
 * timetable already names a teacher for every class and is fetched for the
 * attendance screen anyway, so the lookup happens here rather than being stored a
 * second time in the backend, where the two copies could disagree.
 *
 * A code can be taught by more than one person: `NS1002` appears with MKR, YSK,
 * NRJ and ACM across branches and sections. All of them are returned, because
 * silently picking one would be a guess - and a report grouped by teacher, which
 * the admin section will want, would be wrong.
 *
 * @param code course code, any case
 * @param slots timetable slots
 * @returns one name, several joined, or '' when the grid names nobody
 */
export function instructorFor(
  code: string | undefined | null,
  slots: TimetableSlotWithInstructor[]
): string {
  if (!code || !Array.isArray(slots)) return '';
  const wanted = String(code).trim().toUpperCase();
  const found = new Set<string>();

  for (const slot of slots) {
    if (
      String(slot?.course_code || '')
        .trim()
        .toUpperCase() !== wanted
    )
      continue;
    const name = String(slot.instructor || '').trim();
    // "LAB" is a class type and "VF" a category of teacher, not names.
    if (!name || ['LAB', 'VF', 'STAFF', 'TBA'].includes(name.toUpperCase())) continue;
    for (const part of name.split(/\s+/)) {
      if (part) found.add(part);
    }
  }

  return [...found].sort().join(', ');
}

/** "09:00" -> minutes since midnight, for overlap maths. */
export function toMinutes(value: string | undefined | null): number {
  const [hour, minute] = String(value || '0:0')
    .split(':')
    .map(Number);
  return (Number.isFinite(hour) ? hour : 0) * 60 + (Number.isFinite(minute) ? minute : 0);
}
