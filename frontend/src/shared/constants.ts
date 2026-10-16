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

/**
 * The Settings bundle's registry: what a user can change, and where each
 * change is kept.
 *
 * This is the file a new setting is added to. Each entry carries its own
 * persistence target rather than sharing one, because the feature is delivered
 * in phases: `local` entries are readable today, `server` entries light up when
 * the persistence phase lands. A registry with one hard-coded mechanism would
 * have forced a migration for every setting the day persistence arrived.
 *
 * Kept as data on purpose - the renderer imports it, so exporting a component
 * here would break Fast Refresh.
 */

export type SettingsSectionId = 'appearance' | 'notifications' | 'schedule' | 'privacy' | 'account';

export interface SettingsSection {
  id: SettingsSectionId;
  label: string;
  blurb: string;
  /**
   * A caveat worth stating on the pane itself.
   *
   * Used where a section stores preferences that nothing consumes yet: saying so
   * is the difference between a preference and a promise. Silently implying a
   * feature works is how a settings page loses trust.
   */
  note?: string;
}

export type SettingsValue = string | number | boolean;

export interface SettingsEntry {
  key: string;
  section: SettingsSectionId;
  label: string;
  /** One line under the label saying what the setting does. */
  help: string;
  type: 'boolean' | 'string' | 'number' | 'choice';
  default: SettingsValue;
  /** For `choice`: the allowed values and their labels. */
  choices?: { value: string; label: string }[];
  /** Where the value lives. See the note above. */
  store: 'local' | 'server';
  /**
   * Also keep a device-local copy under the settings key.
   *
   * Only for server-backed settings the app must know before the first render -
   * the theme, or the app paints light and then flips. The server document still
   * wins once it arrives; the copy just makes the first frame correct.
   */
  mirror?: boolean;
  /** Lower sorts first within a section. */
  order?: number;
}

/** The tabs of the Settings page, in order. */
export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  { id: 'appearance', label: 'Appearance', blurb: 'How the app looks on this device.' },
  {
    id: 'notifications',
    label: 'Notifications',
    blurb: 'What the app is allowed to interrupt you for.',
    note: 'Nothing is being sent yet - the app has no alerts channel. These are saved on your account now and will start applying when alerts arrive, so you can set them once.',
  },
  {
    id: 'schedule',
    label: 'Schedule & Attendance',
    blurb: 'How your week and your attendance targets behave.',
  },
  {
    id: 'privacy',
    label: 'Privacy & Data',
    blurb: 'What this device keeps, and what the app is allowed to remember.',
  },
  { id: 'account', label: 'Account', blurb: 'Your programme, branch, security and sign-in.' },
];

/** Every user-facing setting, and the value it falls back to. */
export const SETTINGS_REGISTRY: readonly SettingsEntry[] = [
  // ---------------------------------------------------------- appearance
  {
    key: 'theme',
    section: 'appearance',
    label: 'Theme',
    help: 'Match your system, or pin the app light or dark.',
    type: 'choice',
    default: 'system',
    choices: [
      { value: 'system', label: 'System' },
      { value: 'light', label: 'Light' },
      { value: 'dark', label: 'Dark' },
    ],
    store: 'server',
    // The theme has to be right on the first painted frame, which is before any
    // fetch has resolved.
    mirror: true,
    order: 1,
  },
  {
    key: 'density',
    section: 'appearance',
    label: 'Compact layout',
    help: 'Tighter rows and padding, to fit more on one screen.',
    type: 'boolean',
    default: false,
    store: 'server',
    order: 2,
  },

  // ------------------------------------------------------- notifications
  {
    key: 'notify_class_changes',
    section: 'notifications',
    label: 'Timetable changes',
    help: 'Tell me when a class is moved, added or removed.',
    type: 'boolean',
    default: true,
    store: 'server',
    order: 1,
  },
  {
    key: 'notify_exam_reminders',
    section: 'notifications',
    label: 'Exam reminders',
    help: 'Remind me the day before an exam.',
    type: 'boolean',
    default: true,
    store: 'server',
    order: 2,
  },
  {
    key: 'notify_attendance_drops',
    section: 'notifications',
    label: 'Attendance warnings',
    help: 'Warn me when a subject falls below my target.',
    type: 'boolean',
    default: true,
    store: 'server',
    order: 3,
  },

  // ----------------------------------------------------------- schedule
  {
    key: 'week_start',
    section: 'schedule',
    label: 'Week starts on',
    help: 'The day your timetable week is counted from.',
    type: 'choice',
    default: 'Mon',
    choices: [
      { value: 'Mon', label: 'Monday' },
      { value: 'Sat', label: 'Saturday' },
      { value: 'Sun', label: 'Sunday' },
    ],
    store: 'server',
    order: 1,
  },
  {
    key: 'show_empty_slots',
    section: 'schedule',
    label: 'Show free periods',
    help: 'Keep gaps in the timetable visible instead of collapsing them.',
    type: 'boolean',
    default: false,
    store: 'server',
    order: 2,
  },

  // -------------------------------------------------------------- privacy
  {
    key: 'remember_exam_lookup',
    section: 'privacy',
    label: 'Remember my exam lookup',
    help: 'Keep the last roll-number lookup on this device so a refresh does not ask again.',
    type: 'boolean',
    default: true,
    store: 'server',
    order: 1,
  },
  {
    key: 'reduce_motion',
    section: 'privacy',
    label: 'Reduce motion',
    help: 'Turn off the progress and slide animations. Also respected from your system setting.',
    type: 'boolean',
    default: false,
    store: 'server',
    order: 2,
  },
];

/** The default value of every setting, keyed by setting key. */
export const SETTINGS_DEFAULTS: Record<string, SettingsValue> = SETTINGS_REGISTRY.reduce(
  (acc, entry) => {
    acc[entry.key] = entry.default;
    return acc;
  },
  {} as Record<string, SettingsValue>
);

/** The settings belonging to one section, in display order. */
export function settingsForSection(sectionId: SettingsSectionId): readonly SettingsEntry[] {
  return SETTINGS_REGISTRY.filter(entry => entry.section === sectionId).sort(
    (a, b) => (a.order ?? 0) - (b.order ?? 0)
  );
}

/**
 * Coerce a stored value back to its declared type.
 *
 * Storage is shared with older builds and can be hand-edited, so a boolean
 * setting may arrive as the string "false" - which is truthy and would silently
 * invert the switch. Every read goes through here instead of trusting a cast.
 */
export function coerceSetting(entry: SettingsEntry, raw: unknown): SettingsValue {
  switch (entry.type) {
    case 'boolean':
      if (typeof raw === 'boolean') return raw;
      if (raw === 'true') return true;
      if (raw === 'false') return false;
      return entry.default;
    case 'number': {
      const n = Number(raw);
      return Number.isFinite(n) ? n : entry.default;
    }
    case 'choice': {
      const allowed = entry.choices?.map(choice => choice.value) ?? [];
      return typeof raw === 'string' && allowed.includes(raw) ? raw : entry.default;
    }
    default:
      return typeof raw === 'string' && raw ? raw : entry.default;
  }
}

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
