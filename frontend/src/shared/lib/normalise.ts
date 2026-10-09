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

/** The canonical branch list, used as the fallback for unrecognised input. */
export const BRANCHES = ['CSE A', 'CSE B', 'DS', 'ECE', 'ME', 'SM', 'PG', 'MDes'];

/**
 * Reduce a branch label to its family: "CSE A" and "CSE-B" both become "CSE".
 *
 * `DS` stays `DS` because it is a branch in its own right, not a section of
 * another one - and BDes students must not be folded into anything else.
 */
export function branchFamily(value: string | undefined | null): string {
  if (!value) return '';
  const cleaned = String(value)
    .toUpperCase()
    .replace(/[^A-Z]/g, '')
    .replace(/BTECH|MTECH|MDES|PHD|BDES|SEMESTER|SEM/g, '');
  if (!cleaned) return '';
  // Longest prefix first so "MDES" is not read as "ME".
  for (const prefix of Object.keys(BRANCH_FAMILY).sort((a, b) => b.length - a.length)) {
    if (cleaned.startsWith(prefix)) return BRANCH_FAMILY[prefix];
  }
  return cleaned;
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

/** PG papers are hidden from UG students, and vice versa. */
export function isPostgraduate(value: string | undefined | null): boolean {
  return branchFamily(value) === 'PG';
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
