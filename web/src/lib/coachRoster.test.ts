/**
 * Phase 7 Part 8 — Tests for the coach-email map.
 * The async functions hit the data layer; here we mock fetchJson and
 * exercise the pure resolution logic.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./githubData", () => ({
  fetchJson: vi.fn(),
}));

import { fetchJson } from "./githubData";
import {
  getEmailToCoachMap,
  getCoachToEmailMap,
  resolveCoachByEmail,
} from "./coachRoster";

const mockFile = {
  version: 1,
  emails: {
    "Ella Alexander": "Ella.Alexander@sportsacademy.school",
    "Amir Lewis": "amir.lewis@sportsacademy.school",
  },
};

describe("coachRoster", () => {
  beforeEach(() => {
    vi.mocked(fetchJson).mockReset();
  });

  it("getEmailToCoachMap lowercases emails", async () => {
    vi.mocked(fetchJson).mockResolvedValueOnce(mockFile);
    const map = await getEmailToCoachMap();
    expect(map.get("ella.alexander@sportsacademy.school")).toBe("Ella Alexander");
    expect(map.size).toBe(2);
  });

  it("getCoachToEmailMap keys by display name", async () => {
    vi.mocked(fetchJson).mockResolvedValueOnce(mockFile);
    const map = await getCoachToEmailMap();
    expect(map.get("Ella Alexander")).toBe("ella.alexander@sportsacademy.school");
  });

  it("resolveCoachByEmail is case-insensitive", async () => {
    vi.mocked(fetchJson).mockResolvedValueOnce(mockFile);
    const name = await resolveCoachByEmail("ELLA.ALEXANDER@SPORTSACADEMY.SCHOOL");
    expect(name).toBe("Ella Alexander");
  });

  it("resolveCoachByEmail returns null for unknown email", async () => {
    vi.mocked(fetchJson).mockResolvedValueOnce(mockFile);
    const name = await resolveCoachByEmail("stranger@elsewhere.com");
    expect(name).toBeNull();
  });

  it("resolveCoachByEmail returns null on file fetch failure", async () => {
    vi.mocked(fetchJson).mockRejectedValueOnce(new Error("404"));
    const name = await resolveCoachByEmail("anyone@anywhere.com");
    expect(name).toBeNull();
  });

  it("resolveCoachByEmail returns null for empty/null email", async () => {
    expect(await resolveCoachByEmail(null)).toBeNull();
    expect(await resolveCoachByEmail("")).toBeNull();
  });
});
