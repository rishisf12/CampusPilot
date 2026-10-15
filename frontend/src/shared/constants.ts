/** Shared, non-component data so Fast Refresh stays happy. */

/** Branch dropdown. No bare "CSE" and no duplicates. "DS" is the BDes branch. */
export const BRANCH_OPTIONS = ['CSE A', 'CSE B', 'DS', 'ECE', 'ME', 'SM', 'PG', 'MDes'] as const;

export const PROGRAMMES = ['BTech', 'BDes', 'MTech', 'MDes', 'PhD'] as const;

/**
 * Programme groups, the first question of registration.
 *
 * The three groups are how the app decides what to show: undergraduates get
 * the full classroom toolkit, master's students get classes and exams without
 * the UG machinery, and doctoral scholars get the lightest bundle. Asking
 * first means the rest of signup - and the whole app afterwards - can be
 * shaped around the answer instead of guessing from a branch name.
 */
export const PROGRAMME_GROUPS = ['UG', 'PG', 'PHD'] as const;

/** Which concrete programmes belong to each group. */
export const GROUP_PROGRAMMES: Record<ProgrammeGroup, readonly Programme[]> = {
  UG: ['BTech', 'BDes'],
  PG: ['MTech', 'MDes'],
  PHD: ['PhD'],
};

/** Display details for the programme-chooser cards. */
export const GROUP_DETAILS: Record<
  ProgrammeGroup,
  { title: string; programmes: string; blurb: string }
> = {
  UG: {
    title: 'Undergraduate',
    programmes: 'BTech · BDes',
    blurb: 'Classes, attendance, exams, rooms and teams - the full campus toolkit.',
  },
  PG: {
    title: "Master's",
    programmes: 'MTech · MDes',
    blurb: 'Your classes, timetable and exams - without the undergraduate machinery.',
  },
  PHD: {
    title: 'Doctoral',
    programmes: 'PhD',
    blurb: 'Coursework classes and exams, kept light so research stays in front.',
  },
};

/** The group a concrete programme belongs to. Unknown values fall to UG. */
export function programmeGroupOf(programme: string | undefined | null): ProgrammeGroup {
  const found = PROGRAMME_GROUPS.find(group =>
    GROUP_PROGRAMMES[group].includes((programme || '') as Programme)
  );
  return found || 'UG';
}

/** Branch options offered per concrete programme, at signup. */
export const PROGRAMME_BRANCHES: Record<Programme, readonly BranchOption[]> = {
  BTech: ['CSE A', 'CSE B', 'ECE', 'ME', 'SM'],
  BDes: ['DS'],
  MTech: ['PG'],
  MDes: ['MDes'],
  PhD: ['PG'],
};

export const GENDERS = ['Male', 'Female', 'Other'] as const;

/**
 * How long the "Resend Code" button stays disabled after a signup or a resend.
 *
 * Shared rather than repeated: AuthWrapper starts the clock when a signup
 * completes, and VerifyEmail counts it down, so the two have to agree.
 */
export const RESEND_COOLDOWN_SECONDS = 60;

/** Semester choices per programme. */
export const PROGRAMME_SEMESTERS = {
  BTech: [1, 2, 3, 4, 5, 6, 7, 8],
  BDes: [1, 2, 3, 4, 5, 6, 7, 8],
  MTech: [1, 2, 3, 4],
  MDes: [1, 2, 3, 4],
  PhD: [1, 2],
} as const;

const ROMAN = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII' } as const;

/** `5` -> `"V Sem"`. */
export function semesterLabel(value: number): string {
  return `${ROMAN[value as keyof typeof ROMAN] || value} Sem`;
}

export const ALLOWED_EMAIL_DOMAIN = '@iiitdmj.ac.in';

/** Top-level navigation tabs rendered inside the single header. */
export const NAV_TABS = [
  { id: 'live', label: 'Live Schedule', short: 'Schedule' },
  { id: 'attendance', label: 'Attendance', short: 'Attendance' },
  { id: 'vacant', label: 'Vacant Room Lookup', short: 'Free Rooms' },
  { id: 'exam', label: 'Exam', short: 'Exams' },
] as const;

/**
 * Which classroom tabs each programme group sees.
 *
 * Live Schedule (which carries the shared timetable) and Exam are common ground
 * for everyone. Attendance and Vacant Rooms are built around the undergraduate
 * timetable, so they stay in the UG bundle; a master's or doctoral student is
 * never shown a tab that cannot answer for them.
 */
export const GROUP_CLASSROOM_TABS: Record<ProgrammeGroup, readonly NavTabId[]> = {
  UG: ['live', 'attendance', 'vacant', 'exam'],
  PG: ['live', 'exam'],
  PHD: ['live', 'exam'],
};

/** My Team sub-tabs: discover, own teams, incoming requests, hackathon feed. */
export const TEAM_TABS = [
  { id: 'discover', label: 'Discover' },
  { id: 'mine', label: 'My Teams' },
  { id: 'requests', label: 'Requests' },
  { id: 'feed', label: 'Feed' },
] as const;

/** Skill tags offered when creating a team or editing team-profile skills. */
export const SKILL_OPTIONS = [
  'python',
  'react',
  'nodejs',
  'fastapi',
  'sql',
  'postgres',
  'docker',
  'ml',
  'tensorflow',
  'pandas',
  'flutter',
  'tailwindcss',
  'figma',
] as const;

/**
 * Match-score tone. Thresholds are shared by the card badge and the bar so a
 * score never reads as green in one place and amber in another.
 */
export function toneFor(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 75) return 'success';
  if (score >= 40) return 'warning';
  return 'danger';
}

interface Team {
  is_open: boolean;
  members_count: number;
  max_members: number;
}

/** Open / Full / Pending pill, matching the attendance SAFE badge pattern. */
export function teamStatus(
  team: Team,
  pending: boolean
): { label: string; tone: 'success' | 'warning' | 'danger' } {
  if (pending) return { label: 'PENDING', tone: 'warning' };
  if (!team.is_open) return { label: 'CLOSED', tone: 'danger' };
  if (team.members_count >= team.max_members) return { label: 'FULL', tone: 'danger' };
  return { label: 'OPEN', tone: 'success' };
}

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;

export type BranchOption = (typeof BRANCH_OPTIONS)[number];
export type Programme = (typeof PROGRAMMES)[number];
export type ProgrammeGroup = (typeof PROGRAMME_GROUPS)[number];
export type Gender = (typeof GENDERS)[number];
export type NavTabId = (typeof NAV_TABS)[number]['id'];
export type TeamTabId = (typeof TEAM_TABS)[number]['id'];
export type SkillOption = (typeof SKILL_OPTIONS)[number];
export type Day = (typeof DAYS)[number];
