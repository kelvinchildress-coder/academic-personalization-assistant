/**
 * Phase 7 Part 8 — Tests for session calendar pure helpers.
 * Note: getSessions() is integration-tested separately; here we test the
 * pure functions only.
 */

import { describe, it, expect } from "vitest";
import {
  findCurrentSession,
  findMostRecentSession,
  isCalendarStale,
  sessionDays,
} from "./sessions";
import type { Session } from "./types";

const FIXTURE: Session[] = [
  { id: "2025-26-S5", name: "SY25-26 S5", startDate: "2026-04-27", endDate: "2026-06-05" },
  { id: "2026-27-S1", name: "SY26-27 S1", startDate: "2026-08-12", endDate: "2026-10-02" },
  { id: "2026-27-S2", name: "SY26-27 S2", startDate: "2026-10-13", endDate: "2026-12-18" },
];

describe("findCurrentSession", () => {
  it("returns the session whose range covers the date", () => {
    expect(findCurrentSession(FIXTURE, "2026-05-10")?.id).toBe("2025-26-S5");
  });

  it("is inclusive on the start date", () => {
    expect(findCurrentSession(FIXTURE, "2026-04-27")?.id).toBe("2025-26-S5");
  });

  it("is inclusive on the end date", () => {
    expect(findCurrentSession(FIXTURE, "2026-06-05")?.id).toBe("2025-26-S5");
  });

  it("returns null when no session covers the date", () => {
    expect(findCurrentSession(FIXTURE, "2026-07-01")).toBeNull();
  });
});

describe("findMostRecentSession", () => {
  it("returns the most recently ended session before the date", () => {
    expect(findMostRecentSession(FIXTURE, "2026-07-01")?.id).toBe("2025-26-S5");
  });

  it("returns null when no session has ended before the date", () => {
    expect(findMostRecentSession(FIXTURE, "2026-04-01")).toBeNull();
  });
});

describe("isCalendarStale", () => {
  it("is false when a current session covers the date", () => {
    expect(isCalendarStale(FIXTURE, "2026-05-10")).toBe(false);
  });

  it("is false when no current session but future sessions exist", () => {
    expect(isCalendarStale(FIXTURE, "2026-07-01")).toBe(false);
  });

  it("is true when no current session and no future sessions", () => {
    expect(isCalendarStale(FIXTURE, "2027-01-01")).toBe(true);
  });

  it("is true when sessions list is empty", () => {
    expect(isCalendarStale([], "2026-05-10")).toBe(true);
  });
});

describe("sessionDays", () => {
  it("computes inclusive day count", () => {
    expect(sessionDays(FIXTURE[0])).toBe(40); // Apr 27 → Jun 5 inclusive
    expect(sessionDays(FIXTURE[1])).toBe(52); // Aug 12 → Oct 2 inclusive
  });
});
