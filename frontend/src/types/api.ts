// CampusPilot Frontend — TypeScript type definitions
// Generated from backend OpenAPI spec (90 paths, 48 schemas)

/** Auth types */
export interface UserResponse {
  id: number;
  email: string;
  username: string;
  is_email_verified: boolean;
  full_name?: string;
  roll_number?: string;
  role?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type?: string;
}

export interface StartSignupRequest {
  email: string;
}

export interface VerifySignupRequest {
  email: string;
  code: string;
}

export interface SignupRequest {
  first_name: string;
  last_name: string;
  gender: string;
  programme: string;
  semester: number;
  branch: string;
  username: string;
  roll_number: string;
  email: string;
  password: string;
}

export interface ForgotPasswordRequest {
  identifier: string;
}

export interface ResetPasswordRequest {
  identifier: string;
  code: string;
  new_password: string;
}

export interface VerifyEmailRequest {
  email: string;
  code: string;
}

export interface ResendCodeRequest {
  email: string;
}

/** Profile types */
export interface ProfileResponse {
  id: number;
  semester: number;
  branch: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  programme?: string;
  section?: string;
  elective_codes?: string[];
  attendance_target?: number;
  skills?: string[];
  bio?: string;
  contact?: string;
  original_branch?: string;
  branch_changed_at?: string;
  branch_change_requested?: boolean;
  requested_branch?: string;
  branch_change_reason?: string;
  branch_change_requested_at?: string;
}

export interface ProfileUpdate {
  first_name?: string;
  last_name?: string;
  phone?: string;
  programme?: string;
  semester?: number;
  branch?: string;
  elective_codes?: string[];
  attendance_target?: number;
  skills?: string[];
  bio?: string;
  contact?: string;
}

export interface ProfileOptions {
  branches: string[];
  programmes: string[];
  semester_labels: Record<string, string[]>;
}

export interface BranchChangeRequest {
  from_branch?: string;
  to_branch: string;
  reason?: string;
}

/** Schedule types */
export interface ScheduleNowResponse {
  current_class?: ScheduleClass;
  next_class?: ScheduleClass;
  current_time: string;
  message?: string;
}

export interface ScheduleClass {
  course_code: string;
  course_name: string;
  instructor?: string | null;
  room: string;
  start_time: string;
  end_time: string;
  day: string;
  branch_or_program?: string | null;
}

export interface ExtraCourseResponse {
  code: string;
  name: string;
  semester: number;
  branch: string;
}

export interface ExtraCourseCreate {
  code: string;
  name: string;
  semester: number;
  branch: string;
}

/** Attendance types */
export interface AttendanceRecordRequest {
  course_id: number;
  date: string;
  /** The backend's `AttendanceStatus` enum values. */
  status: 'Present' | 'Absent' | 'Cancelled';
}

/** One row from `GET /attendance/records`. */
export interface AttendanceRecord {
  id: number;
  course_id: number;
  date: string;
  status: 'Present' | 'Absent' | 'Cancelled';
}

export interface AttendanceSummary {
  overall_percentage: number;
  overall_status: string;
  total_present: number;
  total_absent: number;
  courses: AttendanceCourseSummary[];
}

/** The per-course summary dict from `get_course_summary`. */
export interface AttendanceCourseSummary {
  course_id: number;
  course_code: string;
  course_name: string;
  present: number;
  absent: number;
  cancelled: number;
  total_held: number;
  percentage: number;
  status: string;
  can_miss: number;
  must_attend: number;
}

/** One entry of `GET /attendance/subjects`. */
export interface AttendanceSubject {
  course_id: number;
  course_code: string;
  course_name: string;
  present: number;
  absent: number;
  cancelled: number;
  total_held: number;
  percentage: number;
  status: string;
  can_miss: number;
  must_attend: number;
}

/** One entry of the course calendar; `status` is always present per record. */
export interface AttendanceCalendarDay {
  date: string;
  status: 'Present' | 'Absent' | 'Cancelled';
  id?: number;
  day?: string;
  is_multi_period?: boolean;
  is_today?: boolean;
}

export interface AttendanceCourseDetail {
  summary: AttendanceCourseSummary;
  calendar: AttendanceCalendarDay[];
}

/** Timetable types */
export interface TimetableSlot {
  id: number;
  day: string;
  start_time: string;
  end_time: string;
  room: string;
  course_code: string;
  branch_or_program: string;
  semester: number;
  instructor?: string;
}

export interface TimetableOptions {
  branches: string[];
  semesters: number[];
  courses: { code: string; name: string }[];
}

export interface SlotEdit {
  day?: string;
  start_time?: string;
  end_time?: string;
  room?: string;
  course_code?: string;
  branch_or_program?: string;
  semester?: number;
  instructor?: string;
}

/** Exam types - these mirror what the /exam routes actually return. */

export interface ExamProfile {
  branch?: string;
  semester?: number | string;
}

/** One exam row inside a timetable day. */
export interface ExamTimetableRow {
  id?: number | string;
  course_code: string;
  semester?: number | string;
  branch?: string;
  /** `date` for seating, `schedule_date` for the timetable; "unscheduled" for undated rows. */
  date?: string;
  schedule_date?: string;
  day?: string | null;
  room?: string;
  start_time?: string;
  end_time?: string;
  is_extra?: boolean;
  rule?: number | string;
}

export interface ExamDay {
  date?: string;
  day?: string | null;
  exams: ExamTimetableRow[];
}

export interface ExamTimetableResponse {
  total?: number;
  profile?: ExamProfile | null;
  days?: ExamDay[];
}

/** One row of the seating index inside a seating day. */
export interface ExamSeatingRow {
  id?: number | string;
  seating_date?: string;
  room?: string;
  course_code?: string;
  semester?: number | string;
  branch?: string;
  start_time?: string;
  end_time?: string;
  roll_start_prefix?: string;
  roll_start_num?: number;
  roll_end_num?: number;
  is_extra?: boolean;
}

export interface ExamSeatingDay {
  date: string;
  day?: string | null;
  rooms: ExamSeatingRow[];
}

export interface ExamSeatingResponse {
  total?: number;
  profile?: ExamProfile | null;
  days?: ExamSeatingDay[];
}

/** `GET /exam/lookup`: the roll, its exams, and whether the profile filter ran. */
export interface ExamLookupResult {
  roll: string;
  exams: ExamTimetableRow[];
  profile_filter_applied?: boolean;
  rules_used?: string[];
}

/**
 * A lookup result as cached in localStorage so a refresh can restore it.
 * The server remains the source; this is only for display until the next search.
 */
export interface CachedExamLookup {
  roll: string;
  exams: ExamTimetableRow[];
  profileFiltered: boolean;
  profile: ExamProfile | null;
}

export interface ExamClashCourse {
  course_code: string;
  rooms: string[];
  is_extra?: boolean;
}

export interface ExamClash {
  date: string;
  day?: string | null;
  start_time: string;
  end_time: string;
  courses: ExamClashCourse[];
}

/** `GET /exam/clashes`: the personal clash check. */
export interface ExamClashesResponse {
  roll: string;
  exam_count: number;
  exams: ExamTimetableRow[];
  clashes: ExamClash[];
  clash_count?: number;
  dates_affected?: string[];
  involves_extra_course?: boolean;
}

export interface ExamStatus {
  timetable_rows: number;
  seating_rows: number;
  has_timetable?: boolean;
  has_seating?: boolean;
}

/** Rooms types */
export interface VacantRoomResponse {
  mode: 'live' | 'manual';
  day?: string;
  time?: string;
  vacant: string[];
  occupied: string[];
  all: string[];
  has_timetable: boolean;
  message?: string;
}

/** Feedback types */
export interface FeedbackSubmit {
  message: string;
  name?: string;
  phone?: string;
  email?: string;
  subject?: string;
  file?: File | null;
}

export interface FeedbackResponse {
  id: number;
  message: string;
  name?: string;
  phone?: string;
  email?: string;
  subject?: string;
  file_name?: string;
  file_type?: string;
  created_at: string;
  replies: FeedbackReply[];
}

export interface FeedbackReply {
  id: number;
  message: string;
  created_at: string;
  is_admin: boolean;
}

/** Teams types — mirror TeamOut / TeamDetailOut / MatchOut in the backend. */
export interface Team {
  id: number;
  name: string;
  description: string;
  tech_stack: string[];
  wanted: string[];
  max_members: number;
  request_to_join: boolean;
  is_open: boolean;
  hackathon_id?: number | null;
  hackathon?: TeamHackathon | null;
  owner_id?: number | null;
  owner_name?: string | null;
  owner_branch?: string | null;
  members_count: number;
  spots_left: number;
  created_at: string;
}

/** The slim hackathon summary embedded in a team payload. */
export interface TeamHackathon {
  id?: number;
  title?: string;
  ends_at?: string | null;
  is_active?: boolean;
  is_featured?: boolean;
}

export interface TeamCreate {
  name: string;
  description?: string;
  tech_stack?: string[];
  wanted?: string[];
  max_members?: number;
  request_to_join?: boolean;
  hackathon_id?: number | null;
}

/** MemberOut: one row of the team detail member list. */
export interface TeamMember {
  id: number;
  user_id: number;
  username: string;
  full_name?: string | null;
  branch?: string | null;
  skills: string[];
  is_admin: boolean;
  is_approved: boolean;
}

/** Team GET /teams/{id} — TeamDetailOut. */
export interface TeamDetail extends Team {
  members: TeamMember[];
  /** Present on /teams/mine rows; the detail route may omit it. */
  is_owner?: boolean;
}

/** GET /teams/mine — TeamOut flattened with membership flags. */
export interface MyTeam extends Team {
  is_owner: boolean;
  role: string;
}

/** GET /teams/match — TeamOut flattened with match scoring. */
export interface TeamMatchResult extends Team {
  score: number;
  fill_pct: number;
  overlap_pct: number;
  coverage_pct: number;
  branch_bonus: number;
  team_gap: string[];
  matching_skills: string[];
  missing_skills: string[];
  fills_gaps: string[];
  same_branch: boolean;
  reason: string;
}

/** GET /teams/requests — incoming join request. */
export interface TeamJoinRequest {
  id: number;
  status: string;
  message?: string | null;
  created_at: string;
  team_name: string;
  user_name?: string | null;
  user_branch?: string | null;
}

/** Hackathon feed types — GET /hackathons. */
export interface HackathonAttachment {
  name: string;
  url: string;
  size?: number | null;
}

export interface Hackathon {
  id: number;
  title: string;
  sender?: string | null;
  body_text?: string | null;
  subject?: string | null;
  message_id?: string | null;
  attachments: HackathonAttachment[];
  links: string[];
  is_active: boolean;
  is_featured: boolean;
  created_at: string;
  expires_in_days: number;
  teams: number;
  open_teams: number;
  spots_left: number;
}

/** GET /hackathons response envelope. */
export interface HackathonFeed {
  retention_days: number;
  feed_enabled: boolean;
  hackathons: Hackathon[];
}

/** Monitoring types (admin only) */
export interface MonitoringSubsection {
  id: string;
  group: string;
  title: string;
  platform: string;
}

/** API error types */
export interface ApiError {
  detail: string;
}

export interface ValidationError {
  detail: ValidationErrorDetail[];
}

export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** Health check */
export interface HealthResponse {
  status: 'ok';
}
