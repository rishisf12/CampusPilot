/** Shared, non-component data so Fast Refresh stays happy. */

/** Branch dropdown. No bare "CSE" and no duplicates. "DS" is the BDes branch. */
export const BRANCH_OPTIONS = ['CSE A', 'CSE B', 'DS', 'ECE', 'ME', 'SM', 'PG', 'MDes'] as const;

export const PROGRAMMES = ['BTech', 'BDes', 'MTech', 'MDes', 'PhD'] as const;

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
  { id: 'live', label: 'Live Schedule' },
  { id: 'vacant', label: 'Vacant Room Lookup' },
  { id: 'attendance', label: 'Attendance' },
  { id: 'exam', label: 'Exam' },
] as const;

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
export type Gender = (typeof GENDERS)[number];
export type NavTabId = (typeof NAV_TABS)[number]['id'];
export type TeamTabId = (typeof TEAM_TABS)[number]['id'];
export type SkillOption = (typeof SKILL_OPTIONS)[number];
export type Day = (typeof DAYS)[number];
