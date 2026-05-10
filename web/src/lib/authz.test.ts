/**
 * Phase 7 Part 8 — Authz unit tests (rewritten for email-keyed model).
 *
 * The new authz.ts surface (post-Cycle-C-1):
 *   - HEAD_COACH_EMAILS: readonly string[]
 *   - isHeadCoach(email): boolean                                  (pure)
 *   - getRoleForEmail(email): Promise<Role>                        (calls coachRoster)
 *   - coachIdForEmail(email): Promise<string | null>               (calls coachRoster)
 *   - canViewCoach(session, coachId): Promise<boolean>             (calls coachRoster)
 *   - requireCoachOrRedirect(session, coachId): Promise<{...}>     (calls coachRoster)
 *
 * coachRoster.resolveCoachByEmail is mocked so these tests stay pure
 * (no GitHub fetch, no env var requirements).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Session as NextAuthSession } from "next-auth";

// Mock coachRoster BEFORE importing authz so the module graph picks up the mock.
vi.mock("./coachRoster", () => ({
  resolveCoachByEmail: vi.fn(),
}));

import { resolveCoachByEmail } from "./coachRoster";
import {
  HEAD_COACH_EMAILS,
  isHeadCoach,
  getRoleForEmail,
  coachIdForEmail,
  canViewCoach,
  requireCoachOrRedirect,
} from "./authz";

const HEAD_EMAIL = "kelvin.childress@sportsacademy.school";
const COACH_LISA_EMAIL = "lisa.willis@sportsacademy.school";
const COACH_LISA_NAME = "Lisa Willis";
const COACH_LISA_SLUG = "lisa-willis";
const COACH_SAM_NAME = "Sam Jones";
const COACH_SAM_SLUG = "sam-jones";
const STRANGER_EMAIL = "not.a.coach@sportsacademy.school";

function makeSession(email: string | null | undefined): NextAuthSession {
  return {
    user: email === undefined ? undefined : { email: email ?? null },
    expires: "2099-01-01T00:00:00.000Z",
  } as unknown as NextAuthSession;
}

beforeEach(() => {
  vi.mocked(resolveCoachByEmail).mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HEAD_COACH_EMAILS", () => {
  it("contains exactly the hardcoded head coach", () => {
    expect(HEAD_COACH_EMAILS).toEqual([HEAD_EMAIL]);
  });
});

describe("isHeadCoach", () => {
  it("returns true for the hardcoded head-coach email", () => {
    expect(isHeadCoach(HEAD_EMAIL)).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(isHeadCoach("KELVIN.CHILDRESS@SportsAcademy.school")).toBe(true);
  });

  it("returns false for a non-head-coach email", () => {
    expect(isHeadCoach(COACH_LISA_EMAIL)).toBe(false);
  });

  it("returns false for null, undefined, and empty string", () => {
    expect(isHeadCoach(null)).toBe(false);
    expect(isHeadCoach(undefined)).toBe(false);
    expect(isHeadCoach("")).toBe(false);
  });
});

describe("getRoleForEmail", () => {
  it("returns 'head_coach' for the head-coach email without consulting coachRoster", async () => {
    const role = await getRoleForEmail(HEAD_EMAIL);
    expect(role).toBe("head_coach");
    expect(resolveCoachByEmail).not.toHaveBeenCalled();
  });

  it("returns 'coach' when the email maps to a coach name", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(COACH_LISA_NAME);
    const role = await getRoleForEmail(COACH_LISA_EMAIL);
    expect(role).toBe("coach");
    expect(resolveCoachByEmail).toHaveBeenCalledWith(COACH_LISA_EMAIL);
  });

  it("returns 'no_roster' when the email is not in the coach map", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(null);
    const role = await getRoleForEmail(STRANGER_EMAIL);
    expect(role).toBe("no_roster");
  });

  it("returns 'no_roster' for null, undefined, and empty string", async () => {
    expect(await getRoleForEmail(null)).toBe("no_roster");
    expect(await getRoleForEmail(undefined)).toBe("no_roster");
    expect(await getRoleForEmail("")).toBe("no_roster");
    expect(resolveCoachByEmail).not.toHaveBeenCalled();
  });
});

describe("coachIdForEmail", () => {
  it("returns the slug when the email maps to a coach", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(COACH_LISA_NAME);
    const id = await coachIdForEmail(COACH_LISA_EMAIL);
    expect(id).toBe(COACH_LISA_SLUG);
  });

  it("returns null when the email is not in the coach map", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(null);
    const id = await coachIdForEmail(STRANGER_EMAIL);
    expect(id).toBeNull();
  });

  it("returns null for null/undefined/empty input", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValue(null);
    expect(await coachIdForEmail(null)).toBeNull();
    expect(await coachIdForEmail(undefined)).toBeNull();
    expect(await coachIdForEmail("")).toBeNull();
  });
});

describe("canViewCoach", () => {
  it("allows the head coach to view any coach roster", async () => {
    const allowed = await canViewCoach(makeSession(HEAD_EMAIL), COACH_SAM_SLUG);
    expect(allowed).toBe(true);
    // Head-coach short-circuit: no need to consult coachRoster.
    expect(resolveCoachByEmail).not.toHaveBeenCalled();
  });

  it("allows a coach to view their own roster", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(COACH_LISA_NAME);
    const allowed = await canViewCoach(
      makeSession(COACH_LISA_EMAIL),
      COACH_LISA_SLUG,
    );
    expect(allowed).toBe(true);
  });

  it("denies a coach viewing another coach's roster", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(COACH_LISA_NAME);
    const allowed = await canViewCoach(
      makeSession(COACH_LISA_EMAIL),
      COACH_SAM_SLUG,
    );
    expect(allowed).toBe(false);
  });

  it("denies a stranger (email not in coach map)", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(null);
    const allowed = await canViewCoach(
      makeSession(STRANGER_EMAIL),
      COACH_LISA_SLUG,
    );
    expect(allowed).toBe(false);
  });

  it("denies when session has no email", async () => {
    expect(await canViewCoach(makeSession(null), COACH_LISA_SLUG)).toBe(false);
    expect(await canViewCoach(null, COACH_LISA_SLUG)).toBe(false);
  });
});

describe("requireCoachOrRedirect", () => {
  it("redirects to /login when there is no session email", async () => {
    const result = await requireCoachOrRedirect(null, COACH_LISA_SLUG);
    expect(result).toEqual({ ok: false, redirect: "/login" });
    expect(resolveCoachByEmail).not.toHaveBeenCalled();
  });

  it("redirects to /login when session has empty email", async () => {
    const result = await requireCoachOrRedirect(
      makeSession(null),
      COACH_LISA_SLUG,
    );
    expect(result).toEqual({ ok: false, redirect: "/login" });
  });

  it("returns ok=true with empty coachName for the head coach", async () => {
    const result = await requireCoachOrRedirect(
      makeSession(HEAD_EMAIL),
      COACH_SAM_SLUG,
    );
    expect(result).toEqual({ ok: true, coachName: "" });
    expect(resolveCoachByEmail).not.toHaveBeenCalled();
  });

  it("redirects to /no-roster when authenticated email is not in the coach map", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(null);
    const result = await requireCoachOrRedirect(
      makeSession(STRANGER_EMAIL),
      COACH_LISA_SLUG,
    );
    expect(result).toEqual({ ok: false, redirect: "/no-roster" });
  });

  it("redirects a coach to their own roster when they request a different one", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(COACH_LISA_NAME);
    const result = await requireCoachOrRedirect(
      makeSession(COACH_LISA_EMAIL),
      COACH_SAM_SLUG,
    );
    expect(result).toEqual({
      ok: false,
      redirect: `/coach/${COACH_LISA_SLUG}`,
    });
  });

  it("returns ok=true with the canonical coach name for an owner request", async () => {
    vi.mocked(resolveCoachByEmail).mockResolvedValueOnce(COACH_LISA_NAME);
    const result = await requireCoachOrRedirect(
      makeSession(COACH_LISA_EMAIL),
      COACH_LISA_SLUG,
    );
    expect(result).toEqual({ ok: true, coachName: COACH_LISA_NAME });
  });
});
