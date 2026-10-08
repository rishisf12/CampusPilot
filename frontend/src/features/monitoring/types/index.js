// Monitoring feature types

// Subsection types
export const SUBSECTIONS = [
  { id: 'A_W_HEALTH', platform: 'web', group: 'Web App Monitoring', title: 'Health & Performance' },
  { id: 'B_W_ACTIVITY', platform: 'web', group: 'Web App Monitoring', title: 'User Activity & Monetization' },
  { id: 'C_W_SECURITY', platform: 'web', group: 'Web App Monitoring', title: 'Security Monitoring' },
  { id: 'D_W_FEEDBACK', platform: 'web', group: 'Web App Monitoring', title: 'Feedback Analysis' },
  { id: 'A_A_HEALTH', platform: 'android', group: 'Android App Monitoring', title: 'Health & Performance' },
  { id: 'B_A_ACTIVITY', platform: 'android', group: 'Android App Monitoring', title: 'User Activity & Monetization' },
  { id: 'C_A_SECURITY', platform: 'android', group: 'Android App Monitoring', title: 'Security Monitoring' },
  { id: 'D_A_FEEDBACK', platform: 'android', group: 'Android App Monitoring', title: 'Feedback Analysis' },
] as const;

export type SubsectionId = typeof SUBSECTIONS[number]['id'];
export type Platform = 'web' | 'android';

// API response types
export interface SubsectionInfo {
  id: SubsectionId;
  platform: Platform;
  group: string;
  title: string;
}

export interface SubsectionsResponse {
  subsections: SubsectionInfo[];
}

export interface ScanRequest {
  window_days?: number;
  model?: string;
}

export interface ScanResponse {
  scan_id: string;
  subsection: string;
  status: string;
  summary: string;
  findings: Finding[];
  root_causes: string[];
  actions: Action[];
  confidence: Confidence;
  window_start: string;
  window_end: string;
  duration_ms: number;
  model: string;
  created_at: string;
}

export interface Finding {
  title: string;
  severity: 'info' | 'warning' | 'critical';
  evidence: Evidence[];
}

export interface Evidence {
  metric: string;
  value: number;
  unit: string;
  previous_value?: number;
  change_pct?: number;
  window: string;
  source: string;
}

export interface Action {
  action: string;
  priority: 1 | 2 | 3;
  detail: string;
  evidence_refs: string[];
}

export interface Confidence {
  level: 'low' | 'medium' | 'high';
  missing_data: string[];
  tools_failed: string[];
}

// History types
export interface ScanHistoryItem {
  scan_id: string;
  subsection: string;
  status: string;
  summary: string;
  confidence: Confidence;
  window: { start: string; end: string };
  duration_ms: number;
  model: string;
  created_at: string;
}

export interface Incident {
  subsection: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_s: number | null;
  open: boolean;
}

export interface ToolCall {
  scan_id: string;
  tool: string;
  metric_key: string;
  row_count: number;
  ok: boolean;
  at: string;
}

export interface ScanHistoryResponse {
  scans: ScanHistoryItem[];
  incidents: Incident[];
  tool_calls: ToolCall[];
}

// Overview types
export interface OverviewResponse {
  window: { start: string; end: string; days: number };
  platform: Platform | null;
  activity: ActivityOverview;
  security: SecurityOverview;
  revenue: RevenueOverview;
  arpu: ArpuOverview;
  ads: AdsOverview;
  crashes: CrashesOverview;
  health: HealthOverview;
  feedback: FeedbackOverview;
  data_freshness: DataFreshness;
}

export interface ActivityOverview {
  platform: Platform | null;
  window: { start: string; end: string };
  active_users: number;
  active_users_prev: number;
  sessions: number;
  sessions_prev: number;
  events: number;
  new_vs_returning: { total: number; new: number; returning: number };
  retention: Record<string, { pct: number; cohort: number }>;
  countries: { value: string; events: number }[];
  versions: { value: string; events: number }[];
  hourly: { hour: string; events: number }[];
}

export interface SecurityOverview {
  platform: Platform | null;
  window: { start: string; end: string };
  counts: Record<string, number>;
  blocked: Record<string, number>;
}

export interface RevenueOverview {
  platform: Platform | null;
  window: { start: string; end: string };
  revenue_verified_micros: number;
  revenue_unverified_micros: number;
  ad_revenue_micros: number;
  total_revenue_micros: number;
}

export interface ArpuOverview {
  platform: Platform | null;
  window: { start: string; end: string };
  active_users: number;
  arpu_micros: number;
  arpu_prev_micros: number;
  arpu_change_pct: number;
}

export interface AdsOverview {
  platform: Platform | null;
  window: { start: string; end: string };
  impressions: number;
  clicks: number;
  revenue_micros: number;
  ecpm_micros: number;
  ctr_pct: number;
}

export interface CrashesOverview {
  platform: Platform | null;
  window: { start: string; end: string };
  crash_free_rate_pct: number;
  total_sessions: number;
  crashed_sessions: number;
  top_clusters: { exception_type: string; count: number }[];
}

export interface HealthOverview {
  platform: Platform | null;
  window: { start: string; end: string };
  has_data: boolean;
  message?: string;
  uptime_pct?: number;
  response_time_p95_ms?: number;
  http_5xx_pct?: number;
  cpu_pct?: number;
  ram_pct?: number;
  disk_pct?: number;
  crash_free_rate_pct?: number;
  anr_rate_pct?: number;
  startup_time_ms?: number;
  slow_frames_pct?: number;
  ssl_expiry_days?: number;
}

export interface FeedbackOverview {
  window: { start: string; end: string };
  has_data: boolean;
  message?: string;
  total_count?: number;
  sentiment?: { positive: number; neutral: number; negative: number; mean: number };
  top_topics?: { topic: string; count: number }[];
}

export interface DataFreshness {
  now: string;
  latest_rollup_hour: string | null;
  latest_crash_at: string | null;
  rollup_lag_minutes: number | null;
}

export interface MonitoringApi {
  subsections: () => Promise<SubsectionsResponse>;
  overview: (days?: number, platform?: Platform | null) => Promise<OverviewResponse>;
  health: (days: number, platform: Platform) => Promise<any>;
  history: (subsection?: string, limit?: number) => Promise<ScanHistoryResponse>;
  feedback: (days?: number) => Promise<any>;
  monetisation: (days?: number) => Promise<any>;
  rollup: (lookbackHours?: number) => Promise<any>;
}