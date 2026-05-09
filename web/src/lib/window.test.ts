import { describe, expect, it } from "vitest";
import {
  parseWindowParam,
  DEFAULT_WINDOW,
  WINDOW_30D,
  WINDOW_SESSION,
  WINDOW_YEAR,
  ALL_WINDOWS,
} from "./window";

describe("ALL_WINDOWS", () => {
  it("contains exactly the three options in stable order", () => {
    expect(ALL_WINDOWS.map((w) => w.key)).toEqual(["30d", "session", "year"]);
  });

  it("DEFAULT_WINDOW points at the 30-day option", () => {
    expect(DEFAULT_WINDOW).toBe(WINDOW_30D);
  });

  it("each option has a positive integer day count", () => {
    for (const w of ALL_WINDOWS) {
      expect(Number.isInteger(w.days)).toBe(true);
      expect(w.days).toBeGreaterThan(0);
    }
  });

  it("each option has a non-empty label", () => {
    for (const w of ALL_WINDOWS) {
      expect(w.label.length).toBeGreaterThan(0);
    }
  });
});

describe("parseWindowParam", () => {
  it("returns the matching window for each canonical key", () => {
    expect(parseWindowParam("30d")).toBe(WINDOW_30D);
    expect(parseWindowParam("session")).toBe(WINDOW_SESSION);
    expect(parseWindowParam("year")).toBe(WINDOW_YEAR);
  });

  it("is case-insensitive and trims whitespace", () => {
    expect(parseWindowParam("  30D  ")).toBe(WINDOW_30D);
    expect(parseWindowParam("SESSION")).toBe(WINDOW_SESSION);
    expect(parseWindowParam("Year")).toBe(WINDOW_YEAR);
  });

  it("falls back to DEFAULT_WINDOW for unrecognized strings", () => {
    expect(parseWindowParam("14")).toBe(DEFAULT_WINDOW);
    expect(parseWindowParam("forever")).toBe(DEFAULT_WINDOW);
    expect(parseWindowParam("")).toBe(DEFAULT_WINDOW);
    expect(parseWindowParam("   ")).toBe(DEFAULT_WINDOW);
  });

  it("falls back to DEFAULT_WINDOW for null and undefined", () => {
    expect(parseWindowParam(null)).toBe(DEFAULT_WINDOW);
    expect(parseWindowParam(undefined)).toBe(DEFAULT_WINDOW);
  });

  it("uses the first element of an array param", () => {
    expect(parseWindowParam(["session", "year"])).toBe(WINDOW_SESSION);
  });

  it("handles empty arrays as default", () => {
    expect(parseWindowParam([])).toBe(DEFAULT_WINDOW);
  });
});
