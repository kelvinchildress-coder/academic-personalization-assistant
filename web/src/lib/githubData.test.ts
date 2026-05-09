import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  __resetCacheForTests,
  listHistoryDates,
  readRange,
  readSnapshot,
} from "./githubData";
import { GitHubDataError } from "./types";

/**
 * These tests mock global.fetch so no real network is touched.
 * The PAT env var is set to a dummy string for the duration of the suite.
 */

const ORIG_FETCH = global.fetch;
const ORIG_PAT = process.env.GITHUB_DATA_READ_PAT;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function listingBody(dates: string[]) {
  return dates.map((d) => ({
    type: "file",
    name: `${d}.json`,
    path: `data/history/${d}.json`,
    size: 100,
    sha: "deadbeef",
  }));
}

function snapshotFile(date: string, students: unknown[]) {
  const raw = JSON.stringify({ date, students });
  const content = Buffer.from(raw, "utf-8").toString("base64");
  return { type: "file", name: `${date}.json`, content, encoding: "base64" };
}

beforeEach(() => {
  process.env.GITHUB_DATA_READ_PAT = "test-pat";
  __resetCacheForTests();
});

afterEach(() => {
  global.fetch = ORIG_FETCH;
  process.env.GITHUB_DATA_READ_PAT = ORIG_PAT;
});

describe("listHistoryDates", () => {
  it("returns sorted dates from the listing", async () => {
    global.fetch = vi.fn(async () =>
      jsonResponse(200, listingBody(["2026-05-09", "2026-05-07", "2026-05-08"])),
    );

    const dates = await listHistoryDates();
    expect(dates).toEqual(["2026-05-07", "2026-05-08", "2026-05-09"]);
  });

  it("returns an empty list on 404", async () => {
    global.fetch = vi.fn(async () =>
      jsonResponse(404, { message: "Not Found" }),
    );

    const dates = await listHistoryDates();
    expect(dates).toEqual([]);
  });

  it("throws GitHubDataError on 5xx", async () => {
    global.fetch = vi.fn(async () =>
      jsonResponse(503, { message: "Service Unavailable" }),
    );

    await expect(listHistoryDates()).rejects.toBeInstanceOf(GitHubDataError);
  });

  it("ignores non-date filenames in the listing", async () => {
    const body = [
      ...listingBody(["2026-05-07"]),
      { type: "file", name: "README.md", path: "data/history/README.md", size: 10, sha: "abc" },
      { type: "dir", name: "subdir", path: "data/history/subdir", size: 0, sha: "def" },
    ];
    global.fetch = vi.fn(async () => jsonResponse(200, body));

    const dates = await listHistoryDates();
    expect(dates).toEqual(["2026-05-07"]);
  });
});

describe("readSnapshot", () => {
  it("returns the parsed snapshot on 200", async () => {
    global.fetch = vi.fn(async () =>
      jsonResponse(200, snapshotFile("2026-05-08", [{ name: "Alice", coach: "Bob", subjects: [] }])),
    );

    const snap = await readSnapshot("2026-05-08");
    expect(snap?.date).toBe("2026-05-08");
    expect(snap?.students).toHaveLength(1);
    expect(snap?.students[0].name).toBe("Alice");
  });

  it("returns null on 404", async () => {
    global.fetch = vi.fn(async () => jsonResponse(404, { message: "Not Found" }));

    const snap = await readSnapshot("2026-05-08");
    expect(snap).toBeNull();
  });

  it("rejects malformed date strings", async () => {
    global.fetch = vi.fn();
    await expect(readSnapshot("not-a-date")).rejects.toBeInstanceOf(GitHubDataError);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("throws if the body is missing required fields", async () => {
    const raw = JSON.stringify({ date: "2026-05-08" /* no students */ });
    global.fetch = vi.fn(async () =>
      jsonResponse(200, {
        type: "file",
        name: "2026-05-08.json",
        content: Buffer.from(raw, "utf-8").toString("base64"),
        encoding: "base64",
      }),
    );

    await expect(readSnapshot("2026-05-08")).rejects.toBeInstanceOf(GitHubDataError);
  });
});

describe("readRange", () => {
  it("returns only snapshots whose date is within the inclusive range", async () => {
    let callIdx = 0;
    global.fetch = vi.fn(async () => {
      callIdx += 1;
      if (callIdx === 1) {
        return jsonResponse(
          200,
          listingBody(["2026-05-05", "2026-05-08", "2026-05-09", "2026-05-12"]),
        );
      }
      // Subsequent calls are individual snapshot fetches.
      return jsonResponse(200, snapshotFile("2026-05-08", []));
    });

    const snaps = await readRange("2026-05-08", "2026-05-09");
    // Both in-range dates are fetched.
    expect(snaps).toHaveLength(2);
  });

  it("returns empty array when start > end", async () => {
    global.fetch = vi.fn();
    const snaps = await readRange("2026-05-09", "2026-05-08");
    expect(snaps).toEqual([]);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe("auth env requirement", () => {
  it("throws if GITHUB_DATA_READ_PAT is unset", async () => {
    delete process.env.GITHUB_DATA_READ_PAT;
    global.fetch = vi.fn();
    await expect(listHistoryDates()).rejects.toBeInstanceOf(GitHubDataError);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
