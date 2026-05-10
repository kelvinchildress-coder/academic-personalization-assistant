/**
 * Phase 7 Part 3 — Shared TypeScript types matching the Phase 1 history
 * snapshot shape (data/history/YYYY-MM-DD.json).
 *
 * The actual schema in the Python backend lives in src/history.py. Keep
 * these types in sync with that shape; if the Python schema evolves,
 * update here too.
 *
 * Phase 7 Part 8 additions (Cycle A): Session, SubjectTarget, CoachEmailMap.
 * Phase 6 additions (Ask palette): AskKind, AskParams, AskAnswer.
 */

/** Per-subject snapshot for one student on one day. */
export interface SubjectSnap {
  name: string;
  target_xp: number;
  actual_xp: number;
  /** "behind" | "on_track" — matches Python status field. */
  status: string;
  /**
   * Tier label from the Python target cascade. Examples:
   * "personalized_base", "coach_xp_override", "coach_test_by",
   * "age_grade", "year_start_grade".
   */
  tier: string;
}

/** Per-student snapshot. */
export interface StudentSnap {
  name: string;
  coach: string;
  subjects: SubjectSnap[];
}

/** One day's flat snapshot — the contents of one data/history/<date>.json file. */
export interface Snapshot {
  date: string; // ISO YYYY-MM-DD
  students: StudentSnap[];
}

/** Sentinel error type thrown by the data layer for all non-404 failures. */
export class GitHubDataError extends Error {
  readonly status: number | null;
  readonly endpoint: string;
  constructor(message: string, opts: { status: number | null; endpoint: string }) {
    super(message);
    this.name = "GitHubDataError";
    this.status = opts.status;
    this.endpoint = opts.endpoint;
  }
}

/** ---- Phase 7 Part 8 additions ---- */

/** One row from data/sessions.json. Dates are inclusive ISO YYYY-MM-DD. */
export interface Session {
  id: string;
  name: string;
  startDate: string;
  endDate: string;
}

/** Aggregated per-subject target/actual rollup over a window. */
export interface SubjectTarget {
  subject: string;
  /** Average target XP per day across the days observed in the window. */
  avgTargetPerDay: number;
  /** Average actual XP per day across the days observed in the window. */
  avgActualPerDay: number;
  /** avgActualPerDay - avgTargetPerDay (negative = behind). */
  delta: number;
  /** Number of days in the window where the student had a snapshot for this subject. */
  daysObserved: number;
}

/** Shape of config/coach_emails.json. */
export interface CoachEmailFile {
  version: number;
  emails: Record<string, string>;
  _comment?: string;
}

/** ---- Phase 6 additions: Ask palette ---- */

/**
 * The 12 question kinds the /ask palette exposes. Discriminated union
 * driven by the `kind` field on AskParams. Renaming or removing a kind
 * breaks any bookmarked permalink, so additions only — never repurpose.
 */
export type AskKind =
  | "top_xp"
  | "bottom_xp"
  | "deficit_increase"
  | "deficit_decrease"
  | "concern_behind_multiple_days"
  | "concern_deep_deficit"
  | "concern_gap_not_closing"
  | "concern_frequent_exceptions"
  | "no_activity"
  | "student_subject_breakdown"
  | "roster_subject_mix"
  | "clean_window";

/**
 * Params for one ask invocation. The discriminator is `kind`. All params
 * are serializable as URL query string; AskForm encodes/decodes them.
 *
 * `n` is used by top_xp / bottom_xp; defaults to 10 if omitted.
 * `studentName` is used only by student_subject_breakdown.
 *
 * The time window comes from the existing `?w=...` query param via
 * resolveWindow(), not from these params.
 */
export type AskParams =
  | { kind: "top_xp"; n?: number }
  | { kind: "bottom_xp"; n?: number }
  | { kind: "deficit_increase"; n?: number }
  | { kind: "deficit_decrease"; n?: number }
  | { kind: "concern_behind_multiple_days" }
  | { kind: "concern_deep_deficit" }
  | { kind: "concern_gap_not_closing" }
  | { kind: "concern_frequent_exceptions" }
  | { kind: "no_activity" }
  | { kind: "student_subject_breakdown"; studentName: string }
  | { kind: "roster_subject_mix" }
  | { kind: "clean_window" };

/**
 * Result of running one ask. Every variant carries enough info for the
 * UI to render a header + a table with no further computation.
 *
 * `scope.coachFilter` is the coach email used to filter (null = head
 * coach view, sees all). The compute layer applies this filter upstream;
 * answers never include students outside the coach's roster.
 */
export interface AskScope {
  windowLabel: string;
  currentStart: string;
  currentEnd: string;
  priorStart: string | null;
  priorEnd: string | null;
  coachFilter: string | null;
  nStudentsInScope: number;
}

export interface AskRowStudentXp {
  rank: number;
  studentName: string;
  coach: string;
  actualXp: number;
  targetXp: number;
  deficit: number;
  daysPresent: number;
}

export interface AskRowDeficitChange {
  rank: number;
  studentName: string;
  coach: string;
  currentDeficit: number;
  priorDeficit: number;
  delta: number;
}

export interface AskRowConcern {
  studentName: string;
  coach: string;
  daysBehind: number;
  deficit: number;
  severity: number;
}

export interface AskRowNoActivity {
  studentName: string;
  coach: string;
  daysPresent: number;
}

export interface AskRowCleanWindow {
  studentName: string;
  coach: string;
  daysPresent: number;
  actualXp: number;
}

export interface AskRowSubjectStudent {
  subject: string;
  avgTargetPerDay: number;
  avgActualPerDay: number;
  delta: number;
  daysObserved: number;
}

export interface AskRowSubjectRoster {
  subject: string;
  currentAvgActual: number;
  priorAvgActual: number | null;
  delta: number | null;
  nStudents: number;
}

export type AskAnswer =
  | { kind: "top_xp"; scope: AskScope; rows: AskRowStudentXp[] }
  | { kind: "bottom_xp"; scope: AskScope; rows: AskRowStudentXp[] }
  | { kind: "deficit_increase"; scope: AskScope; rows: AskRowDeficitChange[] }
  | { kind: "deficit_decrease"; scope: AskScope; rows: AskRowDeficitChange[] }
  | { kind: "concern_behind_multiple_days"; scope: AskScope; rows: AskRowConcern[] }
  | { kind: "concern_deep_deficit"; scope: AskScope; rows: AskRowConcern[] }
  | { kind: "concern_gap_not_closing"; scope: AskScope; rows: AskRowConcern[] }
  | { kind: "concern_frequent_exceptions"; scope: AskScope; rows: AskRowConcern[] }
  | { kind: "no_activity"; scope: AskScope; rows: AskRowNoActivity[] }
  | {
      kind: "student_subject_breakdown";
      scope: AskScope;
      studentName: string;
      rows: AskRowSubjectStudent[];
    }
  | { kind: "roster_subject_mix"; scope: AskScope; rows: AskRowSubjectRoster[] }
  | { kind: "clean_window"; scope: AskScope; rows: AskRowCleanWindow[] };

/** Human-readable label per kind. Single source of truth for the palette. */
export const ASK_KIND_LABEL: Record<AskKind, string> = {
  top_xp: "Top students by actual XP",
  bottom_xp: "Bottom students by actual XP",
  deficit_increase: "Largest deficit increase vs prior window",
  deficit_decrease: "Largest deficit decrease vs prior window",
  concern_behind_multiple_days: "Students with concern: behind multiple days",
  concern_deep_deficit: "Students with concern: deep deficit",
  concern_gap_not_closing: "Students with concern: gap not closing",
  concern_frequent_exceptions: "Students with concern: frequent exceptions",
  no_activity: "Students with no snapshot in current window",
  student_subject_breakdown: "Subject breakdown for one student",
  roster_subject_mix: "Roster-wide subject XP mix (current vs prior)",
  clean_window: "Clean window (zero days-behind in current window)",
};

/** One-line help text per kind. Used under the palette tile. */
export const ASK_KIND_HELP: Record<AskKind, string> = {
  top_xp: "Highest total actual XP across the current window.",
  bottom_xp: "Lowest total actual XP; excludes students with no snapshots.",
  deficit_increase: "Most growth in deficit (current minus prior).",
  deficit_decrease: "Most reduction in deficit (current minus prior).",
  concern_behind_multiple_days: "Two or more 'behind' subject-days in current window.",
  concern_deep_deficit: "Deficit ≥ 100 XP across current window.",
  concern_gap_not_closing: "Prior had deficit; current deficit is equal or worse.",
  concern_frequent_exceptions: "Three or more subject-days under coach override.",
  no_activity: "Zero snapshots in the current window.",
  student_subject_breakdown: "Per-subject target/actual averages for one student.",
  roster_subject_mix: "Average actual XP per subject across the whole roster.",
  clean_window: "Has snapshots in the current window and never went 'behind'.",
};
