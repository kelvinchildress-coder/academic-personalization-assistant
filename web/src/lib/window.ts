/**
 * Phase 7 Part 6 / Part 8 — Window selector helpers.
 *
 * Maps the `?w=...` URL query param to a concrete day-count + label.
 * Pure module; no React, no environment reads, no githubData.
 *
 * Phase 7 Part 8 additions (Cycle D): WindowResolution + resolveWindow.
 * The legacy WindowKey/ResolvedWindow/parseWindowParam exports are
 * preserved so window.test.ts continues to pass without changes.
 */

import type { Session } from "./types";

// --- Legacy (Part 6) surface — preserved for tests + back-compat. ----------

export type WindowKey = "30d" | "session" | "year";

export interface ResolvedWindow {
  /** Stable key used in URL query strings and component state. */
  key: WindowKey;
  /** Number of days back from `today`, inclusive. */
  days: number;
  /** Human-readable label shown in the UI. */
  label: string;
}

export const WINDOW_30D: ResolvedWindow = {
  key: "30d",
  days: 30,
  label: "Last 30 days",
};

/**
 * Approximate session window. Sessions at TSA are ~6 weeks. We use 42 days
 * as the canonical session length here; if a real session-calendar lookup
 * lands later, swap this constant for a dynamic resolver.
 */
export const WINDOW_SESSION: ResolvedWindow = {
  key: "session",
  days: 42,
  label: "Current session (~6 weeks)",
};

/**
 * Year-to-date approximation. We use 365 days rather than computing the
 * actual school-year boundary.
 */
export const WINDOW_YEAR: ResolvedWindow = {
  key: "year",
  days: 365,
  label: "Last 12 months",
};

export const ALL_WINDOWS: readonly ResolvedWindow[] = [
  WINDOW_30D,
  WINDOW_SESSION,
  WINDOW_YEAR,
] as const;

export const DEFAULT_WINDOW: ResolvedWindow = WINDOW_30D;

/**
 * Parse a raw URL query value into a ResolvedWindow.
 *
 * Rules:
 *   - Case-insensitive; surrounding whitespace trimmed.
 *   - Recognized values: "30d", "session", "year".
 *   - Anything else (null, undefined, empty, garbage) -> DEFAULT_WINDOW.
 */
export function parseWindowParam(
  raw: string | string[] | null | undefined,
): ResolvedWindow {
  if (raw === null || raw === undefined) return DEFAULT_WINDOW;
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (typeof value !== "string") return DEFAULT_WINDOW;
  const norm = value.trim().toLowerCase();
  switch (norm) {
    case "30d":
      return WINDOW_30D;
    case "session":
      return WINDOW_SESSION;
    case "year":
      return WINDOW_YEAR;
    default:
      return DEFAULT_WINDOW;
  }
}

// --- Phase 7 Part 8 — richer window resolution with session calendar. ------

/**
 * Resolved window with concrete date range, used by dashboard pages to
 * call readRange + aggregateRange. Different from ResolvedWindow above
 * because it knows about session ids and computes start/end dates.
 */
export interface WindowResolution {
  /** Echo of the raw param (e.g. "30d", "year", "2025-26-S5"). */
  param: string;
  /** Inclusive ISO date range covered by the current window. */
  currentStart: string;
  currentEnd: string;
  /** Day count for the current window (inclusive). */
  currentDays: number;
  /** Inclusive ISO date range covered by the prior window of equal length. */
  priorStart: string;
  priorEnd: string;
  priorDays: number;
  /** Human-readable label for the UI ("Last 30 days", "SY25-26 Session 5", …). */
  label: string;
}

const ISO_RE = /^\d{4}-\d{2}-\d{2}$/;

function assertIso(d: string, name: string): void {
  if (!ISO_RE.test(d)) {
    throw new Error(`resolveWindow: ${name} must be ISO YYYY-MM-DD, got: ${d}`);
  }
}

function isoMinusDays(iso: string, n: number): string {
  const t = Date.UTC(
    parseInt(iso.slice(0, 4), 10),
    parseInt(iso.slice(5, 7), 10) - 1,
    parseInt(iso.slice(8, 10), 10),
  );
  const d = new Date(t - n * 86_400_000);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function isoDayDiff(start: string, end: string): number {
  const ts = Date.UTC(
    parseInt(start.slice(0, 4), 10),
    parseInt(start.slice(5, 7), 10) - 1,
    parseInt(start.slice(8, 10), 10),
  );
  const te = Date.UTC(
    parseInt(end.slice(0, 4), 10),
    parseInt(end.slice(5, 7), 10) - 1,
    parseInt(end.slice(8, 10), 10),
  );
  return Math.floor((te - ts) / 86_400_000) + 1;
}

/**
 * Resolve a `?w=...` URL parameter against today + the session calendar.
 *
 * Recognized params:
 *   - "30d"            -> last 30 days ending today
 *   - "year"           -> last 365 days ending today
 *   - "<sessionId>"    -> session.startDate..session.endDate (clamped to today
 *                         if the session is current; full range if past)
 *   - anything else    -> falls back to "30d"
 *
 * Prior window has the same length as the current window, ending the day
 * before currentStart.
 */
export function resolveWindow(
  param: string | null | undefined,
  sessions: Session[],
  todayIso: string,
): WindowResolution {
  assertIso(todayIso, "todayIso");
  const norm = (param ?? "30d").trim();
  let currentStart: string;
  let currentEnd: string;
  let label: string;

  // Try to match a session id first.
  const session = sessions.find((s) => s.id === norm);
  if (session) {
    currentStart = session.startDate;
    // Clamp end to today if session is currently active (avoids reading
    // future-dated history files that don't exist yet).
    currentEnd = todayIso < session.endDate ? todayIso : session.endDate;
    label = session.name;
  } else if (norm.toLowerCase() === "year") {
    currentEnd = todayIso;
    currentStart = isoMinusDays(todayIso, 364);
    label = "Last 365 days";
  } else {
    // Default: 30d
    currentEnd = todayIso;
    currentStart = isoMinusDays(todayIso, 29);
    label = "Last 30 days";
  }

  const currentDays = Math.max(1, isoDayDiff(currentStart, currentEnd));

  // Prior window: equal length, ending the day before currentStart.
  const priorEnd = isoMinusDays(currentStart, 1);
  const priorStart = isoMinusDays(priorEnd, currentDays - 1);
  const priorDays = currentDays;

  return {
    param: norm,
    currentStart,
    currentEnd,
    currentDays,
    priorStart,
    priorEnd,
    priorDays,
    label,
  };
}
