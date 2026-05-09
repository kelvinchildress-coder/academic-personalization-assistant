import { describe, expect, it } from "vitest";
import { slugifyName, buildCoachIndex } from "./slug";

describe("slugifyName", () => {
  it("lowercases and hyphenates a normal name", () => {
    expect(slugifyName("Lisa C Willis")).toBe("lisa-c-willis");
  });

  it("strips accents via NFKD normalization", () => {
    expect(slugifyName("José Núñez")).toBe("jose-nunez");
  });

  it("collapses punctuation and runs of whitespace into single hyphens", () => {
    expect(slugifyName("O'Connor,   Ryan")).toBe("o-connor-ryan");
  });

  it("trims leading and trailing hyphens", () => {
    expect(slugifyName("--Lisa Willis--")).toBe("lisa-willis");
  });

  it("returns empty string for null, undefined, empty, or pure-symbol input", () => {
    expect(slugifyName(null)).toBe("");
    expect(slugifyName(undefined)).toBe("");
    expect(slugifyName("")).toBe("");
    expect(slugifyName("   ")).toBe("");
    expect(slugifyName("---")).toBe("");
    expect(slugifyName("!!!")).toBe("");
  });

  it("preserves digits", () => {
    expect(slugifyName("Coach 2")).toBe("coach-2");
  });
});

describe("buildCoachIndex", () => {
  it("returns empty maps for an empty student list", () => {
    const idx = buildCoachIndex([]);
    expect(idx.bySlug.size).toBe(0);
    expect(idx.byName.size).toBe(0);
  });

  it("indexes distinct coaches and provides bidirectional lookup", () => {
    const idx = buildCoachIndex([
      { coach: "Lisa C Willis" },
      { coach: "Lisa C Willis" }, // duplicate, should be deduped
      { coach: "Sam Jones" },
    ]);
    expect(idx.bySlug.get("lisa-c-willis")).toBe("Lisa C Willis");
    expect(idx.bySlug.get("sam-jones")).toBe("Sam Jones");
    expect(idx.byName.get("Lisa C Willis")).toBe("lisa-c-willis");
    expect(idx.byName.get("Sam Jones")).toBe("sam-jones");
    expect(idx.bySlug.size).toBe(2);
    expect(idx.byName.size).toBe(2);
  });

  it("skips students with empty coach names", () => {
    const idx = buildCoachIndex([
      { coach: "Lisa C Willis" },
      { coach: "" },
    ]);
    expect(idx.bySlug.size).toBe(1);
  });

  it("first-seen wins on slug collision", () => {
    // Both names slug to "lisa-willis"; first-seen ("Lisa Willis") wins.
    const idx = buildCoachIndex([
      { coach: "Lisa Willis" },
      { coach: "Lisa-Willis" },
    ]);
    expect(idx.bySlug.get("lisa-willis")).toBe("Lisa Willis");
    expect(idx.byName.get("Lisa Willis")).toBe("lisa-willis");
    expect(idx.byName.has("Lisa-Willis")).toBe(false);
    expect(idx.bySlug.size).toBe(1);
  });
});
