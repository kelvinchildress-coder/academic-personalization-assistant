/**
 * Phase 7 Part 8 — Session calendar lookup.
 *
 * Reads data/sessions.json via the GitHub data layer and exposes pure
 * helpers for finding the current session, listing sessions, and detecting
 * a stale calendar (no session covers today and no future sessions exist).
 */

import "server-only";
import type { Session } from "./types";
import { fetchJson } from "./githubData";

interface SessionsFile {
  version: number;
  sessions: Session[];
  _comment?: string;
}

/**
 * Fetch the session calendar from data/sessions.json. Returns sessions
 * sorted by startDate ascending. Returns [] if the file is missing or
 * malformed (caller should treat empty as a stale-calendar signal).
 */
export async function getSessions(): Promise<Session[]> {
  try {
    const raw = await fetchJson<SessionsFile>("data/sessions.json");
    if (!raw || !Array.isArray(raw.sessions)) return [];
    return [...raw.sessions].sort((a, b) =>
      a.startDate.localeCompare(b.startDate)
    );
  } catch {
    return [];
  }
}

/**
 * Find the session that contains the given ISO date (YYYY-MM-DD), inclusive
 * on both ends. Returns null if no session covers that date.
 */
export function findCurrentSession(
  sessions: Session[],
  isoDate: string
): Session | null {
  for (const s of sessions) {
    if (isoDate >= s.startDate && isoDate <= s.endDate) return s;
  }
  return null;
}

/**
 * Find the most recently-ended session whose endDate is strictly before
 * the given date. Used as a fallback when today falls between sessions.
 */
export function findMostRecentSession(
  sessions: Session[],
  isoDate: string
): Session | null {
  const past = sessions.filter((s) => s.endDate < isoDate);
  if (past.length === 0) return null;
  return past[past.length - 1];
}

/**
 * Return true if the calendar is "stale" — i.e. no session covers today
 * AND no future sessions exist after today. The dashboard surfaces a
 * banner to the head coach in this case.
 */
export function isCalendarStale(
  sessions: Session[],
  isoDate: string
): boolean {
  if (sessions.length === 0) return true;
  const current = findCurrentSession(sessions, isoDate);
  const hasFuture = sessions.some((s) => s.startDate > isoDate);
  return !current && !hasFuture;
}

/**
 * Number of days between two inclusive ISO dates (YYYY-MM-DD).
 * Returns at least 1.
 */
export function sessionDays(s: Session): number {
  const start = new Date(s.startDate + "T00:00:00Z").getTime();
  const end = new Date(s.endDate + "T00:00:00Z").getTime();
  const days = Math.floor((end - start) / 86400000) + 1;
  return Math.max(1, days);
}
