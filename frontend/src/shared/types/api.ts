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
  /** The year the student joined, e.g. 2024 - the batch they belong to. */
  batch_year?: number;
  username: string;
  roll_number: string;
  whatsapp: string;
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
  /** The year the student joined, e.g. 2024 - the batch they belong to. */
  batch_year?: number | null;
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
  batch_year?: number | null;
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
  /** Programme group (UG/PG/PHD) -> the programmes it contains. */
  programme_groups: Record<string, string[]>;
  /** Programme -> the branches it offers. */
  programme_branches: Record<string, string[]>;
  /** Programme -> the semesters it offers. */
  programme_semesters: Record<string, number[]>;
  semesters: Array<{ value: number; label: string }>;
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
  id: number;
  code: string;
  name: string;
  instructor?: string;
  is_elective: boolean;
  is_extra: boolean;
  semester?: number;
  branch?: string;
}

export interface ExtraCourseCreate {
  code: string;
  name: string;
  instructor?: string;
  semester?: number;
  branch?: string;
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
  instructor?: string;
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

/** `GET /exam/options`: branch / semester / course options from uploaded exam data. */
export interface ExamOptions {
  branches: string[];
  branch_counts: Record<string, number>;
  semesters: number[];
  courses: string[];
  total_rows: number;
}

/** One exam timetable slot (ungrouped) from `GET /exam/slots` or `PUT /exam/slot/{id}`. */
export interface ExamSlotResponse {
  id: number;
  schedule_date: string | null;
  day: string | null;
  start_time: string | null;
  end_time: string | null;
  room: string | null;
  course_code: string | null;
  branch: string | null;
  semester: number | null;
  is_extra: boolean;
}

/** Fields editable on `PUT /exam/slot/{id}`. */
export interface ExamSlotEdit {
  schedule_date?: string;
  start_time?: string;
  end_time?: string;
  room?: string;
  course_code?: string;
  branch?: string;
  semester?: number;
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

// ============================================================================
// OppFeed Types
// ============================================================================

/** A single opportunity card for the faculty feed. */
export interface OpportunityCard {
  slug: string;
  title: string;
  organization_name: string;
  organization_logo_url: string | null;
  opportunity_type: string;
  location: string | null;
  work_mode: string | null;
  stipend_min: number | null;
  stipend_max: number | null;
  stipend_currency: string;
  stipend_period: string | null;
  registration_deadline: string | null;
  deadline_type: string;
  short_summary: string | null;
  eligibility_summary: string | null;
  skills_required: string[];
  tags: string[];
  apply_url: string;
  days_until_deadline: number | null;
}

/** Full opportunity detail for faculty view. */
export interface OpportunityDetail {
  slug: string;
  title: string;
  organization_name: string;
  organization_logo_url: string | null;
  banner_url: string | null;
  opportunity_type: string;
  short_summary: string | null;
  full_description: string | null;
  location: string | null;
  work_mode: string | null;
  duration: string | null;
  start_date: string | null;
  stipend_min: number | null;
  stipend_max: number | null;
  stipend_currency: string;
  stipend_period: string | null;
  stipend_notes: string | null;
  registration_start_date: string | null;
  registration_deadline: string | null;
  deadline_type: string;
  education_levels: string[];
  allowed_branches: string[];
  graduation_years: number[];
  min_cgpa_or_percentage: number | null;
  other_criteria: string | null;
  open_to_countries: string[];
  skills_required: string[];
  perks_benefits: string[];
  selection_process: string | null;
  documents_required: string[];
  how_to_apply: string | null;
  apply_url: string;
  secondary_sources: string[];
  contact_email: string | null;
  tags: string[];
  attachments: Array<Record<string, unknown>>;
  published_at: string | null;
  days_until_deadline: number | null;
}

/** Admin opportunity list item. */
export interface OpportunityListItem {
  id: number;
  slug: string;
  title: string;
  organization_name: string;
  opportunity_type: string;
  status: string;
  confidence_score: number | null;
  source_domain: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Full opportunity detail for admin. */
export interface OpportunityDetailAdmin {
  id: number;
  slug: string;
  title: string;
  organization_name: string;
  organization_logo_url: string | null;
  banner_url: string | null;
  opportunity_type: string;
  status: string;
  short_summary: string | null;
  full_description: string | null;
  location: string | null;
  work_mode: string | null;
  duration: string | null;
  start_date: string | null;
  stipend_min: number | null;
  stipend_max: number | null;
  stipend_currency: string;
  stipend_period: string | null;
  stipend_notes: string | null;
  registration_start_date: string | null;
  registration_deadline: string | null;
  deadline_type: string;
  education_levels: string[];
  allowed_branches: string[];
  graduation_years: number[];
  min_cgpa_or_percentage: number | null;
  other_criteria: string | null;
  open_to_countries: string[];
  skills_required: string[];
  perks_benefits: string[];
  selection_process: string | null;
  documents_required: string[];
  how_to_apply: string | null;
  apply_url: string;
  secondary_sources: string[];
  attachments: Array<Record<string, unknown>>;
  contact_email: string | null;
  source_domain: string | null;
  verified_at: string | null;
  verification_report: Record<string, unknown> | null;
  confidence_score: number | null;
  field_evidence: Record<string, unknown> | null;
  llm_provider: string | null;
  llm_model: string | null;
  prompt_version: string | null;
  tags: string[];
  version: number;
  created_by_run_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  published_at: string | null;
  scheduled_publish_at: string | null;
}

/** Paginated opportunities response. */
export interface PaginatedOpportunities {
  items: OpportunityCard[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Available filter values for the feed. */
export interface FeedFilters {
  opportunity_types: string[];
  locations: string[];
  work_modes: string[];
  education_levels: string[];
  allowed_branches: string[];
  graduation_years: number[];
  skills: string[];
}

/** Opportunity filter parameters. */
export interface OpportunityFilterParams {
  page?: number;
  page_size?: number;
  status?: string;
  opportunity_type?: string;
  search?: string;
  source_domain?: string;
  date_from?: string;
  date_to?: string;
}

/** Admin: Update opportunity request. */
export interface OpportunityUpdateRequest {
  title?: string;
  short_summary?: string;
  full_description?: string;
  location?: string;
  work_mode?: string;
  duration?: string;
  stipend_min?: number;
  stipend_max?: number;
  stipend_currency?: string;
  stipend_period?: string;
  registration_deadline?: string;
  deadline_type?: string;
  education_levels?: string[];
  allowed_branches?: string[];
  graduation_years?: number[];
  skills_required?: string[];
  perks_benefits?: string[];
  how_to_apply?: string;
  apply_url?: string;
  tags?: string[];
  attachments?: Array<Record<string, unknown>>;
  scheduled_publish_at?: string;
}

/** Admin: Bulk action request. */
export interface BulkActionRequest {
  ids: number[];
  action: string; // approve, reject, publish, schedule, archive, delete
  scheduled_publish_at?: string;
}

/** Admin: State transition request. */
export interface StateTransitionRequest {
  action: string; // approve, reject, publish, schedule, archive
  scheduled_publish_at?: string;
  reason?: string;
}

/** Admin: Run list item. */
export interface RunListItem {
  run_id: string;
  status: string;
  mode: string;
  started_at: string | null;
  completed_at: string | null;
  opportunities_found: number;
  opportunities_verified: number;
  opportunities_rejected: number;
  opportunities_drafted: number;
  opportunities_published: number;
  /** Where the run has got to, and how far it has to go. */
  current_stage?: string | null;
  stages_completed?: number;
  total_stages?: number;
}

/** Admin: Full run detail. */
export interface RunResponse {
  run_id: string;
  status: string;
  mode: string;
  started_at: string | null;
  completed_at: string | null;
  opportunities_found: number;
  opportunities_verified: number;
  opportunities_rejected: number;
  opportunities_drafted: number;
  opportunities_published: number;
  errors: string[] | null;
  llm_calls: number;
  llm_tokens: number;
  current_stage: string | null;
  steps: RunStepResponse[];
}

/** Admin: Run step detail. */
export interface RunStepResponse {
  step_name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  llm_provider: string | null;
  llm_model: string | null;
}

/** Admin: Create run request. */
export interface RunCreateRequest {
  mode: string; // manual | dry_run
}

/** Admin: Agent settings. */
export interface AgentSettingsResponse {
  run_window_start: string;
  run_window_end: string;
  auto_publish_enabled: boolean;
  auto_publish_threshold: number;
  llm_provider_chain: string;
  llm_max_rpm: number;
  /** How many verified opportunities one run may write. */
  max_drafts_per_run: number;
  enable_agent: boolean;
  enable_scheduler: boolean;
  enable_vision: boolean;
  enable_banner_gen: boolean;
  enable_audio_summary: boolean;
}

/** Admin: Agent settings update request. */
export interface AgentSettingsUpdateRequest {
  run_window_start?: string;
  run_window_end?: string;
  auto_publish_enabled?: boolean;
  auto_publish_threshold?: number;
  llm_provider_chain?: string;
  llm_max_rpm?: number;
  max_drafts_per_run?: number;
  enable_agent?: boolean;
  enable_scheduler?: boolean;
  enable_vision?: boolean;
  enable_banner_gen?: boolean;
  enable_audio_summary?: boolean;
}

/** Admin: Source rule. */
export interface SourceRuleResponse {
  id: number;
  domain: string;
  rule_type: string; // allow | deny
  enabled: boolean;
  description: string | null;
  created_at: string | null;
}

/** Admin: Source rule create request. */
export interface SourceRuleCreateRequest {
  domain: string;
  rule_type: string; // allow | deny
  description?: string;
}

/** Admin: Source rule update request. */
export interface SourceRuleUpdateRequest {
  enabled?: boolean;
  description?: string;
}

/** Admin: Search query. */
export interface SearchQueryResponse {
  id: number;
  query: string;
  category: string | null;
  enabled: boolean;
  is_seed: boolean;
  priority: number;
  created_at: string | null;
}

/** Admin: Search query create request. */
export interface SearchQueryCreateRequest {
  query: string;
  category?: string;
  enabled?: boolean;
  is_seed?: boolean;
  priority?: number;
}

/** Admin: Search query update request. */
export interface SearchQueryUpdateRequest {
  query?: string;
  category?: string;
  enabled?: boolean;
  priority?: number;
}

/** Admin: LLM provider health. */
export interface ProviderHealth {
  provider: string;
  status: string; // healthy | degraded | unavailable
  model: string;
  latency_ms: number | null;
  last_checked: string | null;
  error: string | null;
  rate_limit_remaining: number | null;
  rate_limit_total: number | null;
}

/** Admin: LLM status response. */
export interface LLMStatusResponse {
  providers: ProviderHealth[];
  active_provider: string;
  cache_hit_rate: number;
  total_calls_today: number;
}

/** Admin: LLM test request/response. */
export interface LLMTestRequest {
  provider?: string;
  prompt: string;
}

export interface LLMTestResponse {
  provider: string;
  model: string;
  success: boolean;
  response: string | null;
  latency_ms: number | null;
  error: string | null;
}

/** Admin: Feedback detail. */
export interface OppFeedFeedbackResponse {
  id: number;
  opportunity_id: number;
  version: number;
  thumbs_up: boolean | null;
  rating: number | null;
  tags: string[];
  comment: string | null;
  applied_as_instruction: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** Admin: Feedback create request. */
export interface OppFeedFeedbackCreateRequest {
  thumbs_up?: boolean;
  rating?: number;
  tags?: string[];
  comment?: string;
}

/** The administrator's own profile: an operator's, not a student's. */
export interface AdminProfileResponse {
  id: number;
  user_id?: number | null;
  email: string;
  role: string;
  display_name?: string | null;
  job_title?: string | null;
  team?: string | null;
  timezone: string;
  locale: string;
  theme: 'system' | 'light' | 'dark';
  density: 'comfortable' | 'compact';
  default_subsection?: string | null;
  default_window_days: number;
  pinned_panels: string[];
  notify_email?: string | null;
  notify_channels: string[];
  quiet_hours: Record<string, unknown>;
  notes?: string | null;
  /** Their account's own state. */
  account_created_at?: string | null;
  passkey_registered: boolean;
  own_action_count: number;
  recent_actions: AdminActivityItem[];
}

/** What an administrator may change about their own profile. */
export interface AdminProfileUpdate {
  display_name?: string | null;
  job_title?: string | null;
  team?: string | null;
  timezone?: string | null;
  locale?: string | null;
  theme?: 'system' | 'light' | 'dark';
  density?: 'comfortable' | 'compact';
  default_subsection?: string | null;
  default_window_days?: number;
  pinned_panels?: string[];
  notify_email?: string | null;
  notify_channels?: string[];
  quiet_hours?: Record<string, unknown>;
  notes?: string | null;
}

/** One of the administrator's own actions. */
export interface AdminActivityItem {
  id: number;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  at?: string | null;
}

// ---------------------------------------------------------------- mail
// The mail app: section inboxes fed by the college's mailboxes. Kept apart
// from feedback on purpose - mail keeps the message, feedback turns it into
// a row.

export interface MailAttachmentMeta {
  /** In a message's response: the stored file, so a download can point at it. */
  id?: number;
  filename: string;
  content_type?: string | null;
  size?: number | null;
}

export interface MailMessageResponse {
  id: number;
  message_id: string;
  group: string;
  group_label: string;
  section: string;
  section_label: string;
  direction: string;
  from_email: string;
  from_name?: string | null;
  to_email?: string | null;
  subject?: string | null;
  snippet?: string | null;
  body_text?: string | null;
  body_html?: string | null;
  received_at?: string | null;
  is_read: boolean;
  is_starred: boolean;
  has_attachments: boolean;
  attachments: MailAttachmentMeta[];
  labels: string[];
}

export interface MailSectionInfo {
  id: string;
  label: string;
  count: number;
  unread: number;
}

export interface MailGroupInfo {
  id: string;
  label: string;
}

export interface MailListResponse {
  total: number;
  page: number;
  size: number;
  messages: MailMessageResponse[];
  groups: MailGroupInfo[];
  sections: MailSectionInfo[];
  unread: Record<string, number>;
  starred_count: number;
}

export interface MailComposeRequest {
  to?: string;
  subject?: string;
  body?: string;
  section?: string | null;
  /** The message this one answers: the backend takes the recipient's address from it. */
  reply_of?: number;
  /** The message this one passes on: the subject gains Fwd:, the body quotes it. */
  forward_of?: number;
}

/** One attachment, as the Files (Downloads) view shows it. */
export interface MailFileInfo {
  id: number;
  message_id: number;
  filename: string;
  content_type?: string | null;
  size: number;
  section: string;
  group: string;
  from_email: string;
  from_name?: string | null;
  subject?: string | null;
  received_at?: string | null;
}
