/**
 * Phase 7 Part 6 — Window selector helpers.
 *
 * Maps the `?window=...` URL query param to a concrete day-count + label.
 * Pure module; no React, no environment reads, no githubData.
 */

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
 * actual school-year boundary. This intentionally over-counts on dates
 * before the SY start; per Q4-2 we already exclude S1-4 of SY25-26 from
 * tracked data, so the practical effect is bounded.
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
 *
 * Why pure-string-key matching instead of numeric parsing? Because the
 * URL is a stable contract; we don't want a typo'd "?window=14" to
 * silently produce a 14-day window that no UI button can re-select.
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
