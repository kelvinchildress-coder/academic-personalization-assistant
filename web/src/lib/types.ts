/**
 * Phase 7 Part 3 — Shared TypeScript types matching the Phase 1 history
 * snapshot shape (data/history/YYYY-MM-DD.json).
 *
 * The actual schema in the Python backend lives in src/history.py. Keep
 * these types in sync with that shape; if the Python schema evolves,
 * update here too.
 *
 * Phase 7 Part 8 additions (Cycle A): Session, SubjectTarget, CoachEmailMap.
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
