import { describe, expect, it } from "vitest";
import {
  HEAD_COACH_EMAILS,
  isHeadCoach,
  canViewCoachRoster,
} from "./authz";

describe("HEAD_COACH_EMAILS", () => {
  it("contains exactly the hardcoded head coach", () => {
    expect(HEAD_COACH_EMAILS).toEqual([
      "kelvin.childress@sportsacademy.school",
    ]);
  });
});

describe("isHeadCoach", () => {
  it("returns true for the hardcoded head-coach email", () => {
    expect(isHeadCoach("kelvin.childress@sportsacademy.school")).toBe(true);
  });

  it("is case-insensitive and trims whitespace", () => {
    expect(isHeadCoach("  KELVIN.CHILDRESS@SportsAcademy.school  ")).toBe(true);
  });

  it("returns false for a non-head-coach email", () => {
    expect(isHeadCoach("lisa.willis@sportsacademy.school")).toBe(false);
  });

  it("returns false for null, undefined, or empty string", () => {
    expect(isHeadCoach(null)).toBe(false);
    expect(isHeadCoach(undefined)).toBe(false);
    expect(isHeadCoach("")).toBe(false);
    expect(isHeadCoach("   ")).toBe(false);
  });
});

describe("canViewCoachRoster", () => {
  it("allows head coach to view any roster", () => {
    expect(
      canViewCoachRoster(
        "kelvin.childress@sportsacademy.school",
        "lisa.willis@sportsacademy.school",
      ),
    ).toBe(true);
  });

  it("allows a coach to view their own roster (case-insensitive)", () => {
    expect(
      canViewCoachRoster(
        "Lisa.Willis@sportsacademy.school",
        "lisa.willis@sportsacademy.school",
      ),
    ).toBe(true);
  });

  it("denies a coach viewing another coach's roster", () => {
    expect(
      canViewCoachRoster(
        "lisa.willis@sportsacademy.school",
        "sam.jones@sportsacademy.school",
      ),
    ).toBe(false);
  });

  it("denies when viewer email is missing", () => {
    expect(
      canViewCoachRoster(null, "lisa.willis@sportsacademy.school"),
    ).toBe(false);
    expect(
      canViewCoachRoster("", "lisa.willis@sportsacademy.school"),
    ).toBe(false);
  });

  it("denies when target email is missing (non-head viewer)", () => {
    expect(
      canViewCoachRoster("lisa.willis@sportsacademy.school", null),
    ).toBe(false);
    expect(
      canViewCoachRoster("lisa.willis@sportsacademy.school", ""),
    ).toBe(false);
  });

  it("allows head coach even when target email is missing", () => {
    // Head coach has blanket access; missing target shouldn't block them.
    expect(
      canViewCoachRoster("kelvin.childress@sportsacademy.school", null),
    ).toBe(true);
  });
});
