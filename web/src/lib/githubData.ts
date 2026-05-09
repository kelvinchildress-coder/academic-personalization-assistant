import "server-only";

import { GitHubDataError, type Snapshot } from "./types";

/**
 * Phase 7 Part 3 — Server-only GitHub data reader.
 *
 * Reads daily history snapshots (data/history/YYYY-MM-DD.json) from the
 * fixed repo via the GitHub Contents API, using a fine-grained PAT
 * scoped to Contents:Read-only on this repo only.
 *
 * The `import "server-only"` line above causes the build to fail if
 * this module is ever imported from a Client Component or any code that
 * ends up in the browser bundle.
 *
 * API surface (read-only):
 *   - listHistoryDates(): Promise<string[]>
 *   - readSnapshot(dateIso): Promise<Snapshot | null>
 *   - readRange(startIso, endIso): Promise<Snapshot[]>
 *
 * There are intentionally NO write methods on this module.
 */

// ---------------------------------------------------------------------------
// Constants. Owner/repo and history path are architectural, not per-deploy.
// ---------------------------------------------------------------------------
const REPO_OWNER = "kelvinchildress-coder";
const REPO_NAME = "academic-personalization-assistant";
const HISTORY_PATH = "data/history";
const REPO_REF = "main";

const GITHUB_API = "https://api.github.com";

// 60-second in-memory cache TTL. Per-instance (no cross-region sharing).
const CACHE_TTL_MS = 60 * 1000;

// ---------------------------------------------------------------------------
// Cache. Module-level Maps; survive across requests on a warm Vercel instance.
// ---------------------------------------------------------------------------
type CacheEntry<T> = { value: T; expiresAt: number };

const listingCache: { current: CacheEntry<string[]> | null } = { current: null };
const snapshotCache = new Map<string, CacheEntry<Snapshot | null>>();

function isFresh<T>(entry: CacheEntry<T> | null | undefined): boolean {
  return !!entry && entry.expiresAt > Date.now();
}

function setCache<T>(
  store: { current: CacheEntry<T> | null } | Map<string, CacheEntry<T>>,
  keyOrNull: string | null,
  value: T,
): void {
  const entry: CacheEntry<T> = { value, expiresAt: Date.now() + CACHE_TTL_MS };
  if (keyOrNull === null) {
    (store as { current: CacheEntry<T> | null }).current = entry;
  } else {
    (store as Map<string, CacheEntry<T>>).set(keyOrNull, entry);
  }
}

// ---------------------------------------------------------------------------
// Internal: authenticated GitHub fetch.
// ---------------------------------------------------------------------------
function authHeader(): Record<string, string> {
  const token = process.env.GITHUB_DATA_READ_PAT;
  if (!token) {
    throw new GitHubDataError(
      "GITHUB_DATA_READ_PAT is not set. The dashboard cannot read history.",
      { status: null, endpoint: "(env)" },
    );
  }
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

type ContentsResponseFile = {
  type: "file";
  name: string;
  path: string;
  size: number;
  sha: string;
  // Base64-encoded content when fetching a single file.
  content?: string;
  encoding?: "base64";
};

type ContentsResponseList = ContentsResponseFile[];

async function ghFetch(endpoint: string): Promise<Response> {
  const url = `${GITHUB_API}${endpoint}`;
  // Note: `cache: "no-store"` defers caching to OUR module-level cache.
  // We do NOT want Next.js to also cache responses on disk because the
  // PAT could be embedded into cached headers in some setups.
  return fetch(url, {
    headers: authHeader(),
    cache: "no-store",
  });
}

// ---------------------------------------------------------------------------
// Public: listHistoryDates
// ---------------------------------------------------------------------------
const DATE_FILENAME_RE = /^(\d{4}-\d{2}-\d{2})\.json$/;

/**
 * List every YYYY-MM-DD for which a history snapshot exists, sorted ascending.
 * Cached for 60 seconds.
 */
export async function listHistoryDates(): Promise<string[]> {
  if (isFresh(listingCache.current)) {
    return listingCache.current!.value;
  }

  const endpoint =
    `/repos/${REPO_OWNER}/${REPO_NAME}/contents/${HISTORY_PATH}` +
    `?ref=${REPO_REF}`;
  const resp = await ghFetch(endpoint);

  if (resp.status === 404) {
    // No history directory yet — empty list, still cache it.
    setCache(listingCache, null, []);
    return [];
  }
  if (!resp.ok) {
    throw new GitHubDataError(
      `Failed to list history (HTTP ${resp.status}).`,
      { status: resp.status, endpoint },
    );
  }

  const body = (await resp.json()) as ContentsResponseList;
  const dates: string[] = [];
  for (const entry of body) {
    if (entry.type !== "file") continue;
    const m = DATE_FILENAME_RE.exec(entry.name);
    if (m) dates.push(m[1]);
  }
  dates.sort();

  setCache(listingCache, null, dates);
  return dates;
}

// ---------------------------------------------------------------------------
// Public: readSnapshot
// ---------------------------------------------------------------------------
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Read one day's snapshot. Returns null if the file does not exist.
 * Cached for 60 seconds per date.
 */
export async function readSnapshot(dateIso: string): Promise<Snapshot | null> {
  if (!ISO_DATE_RE.test(dateIso)) {
    throw new GitHubDataError(
      `Invalid date format: ${dateIso} (expected YYYY-MM-DD).`,
      { status: null, endpoint: "(input)" },
    );
  }

  const cached = snapshotCache.get(dateIso);
  if (isFresh(cached)) {
    return cached!.value;
  }

  const endpoint =
    `/repos/${REPO_OWNER}/${REPO_NAME}/contents/${HISTORY_PATH}/${dateIso}.json` +
    `?ref=${REPO_REF}`;
  const resp = await ghFetch(endpoint);

  if (resp.status === 404) {
    setCache(snapshotCache, dateIso, null);
    return null;
  }
  if (!resp.ok) {
    throw new GitHubDataError(
      `Failed to read snapshot ${dateIso} (HTTP ${resp.status}).`,
      { status: resp.status, endpoint },
    );
  }

  const body = (await resp.json()) as ContentsResponseFile;
  if (!body.content || body.encoding !== "base64") {
    throw new GitHubDataError(
      `Unexpected response shape for ${dateIso}.`,
      { status: resp.status, endpoint },
    );
  }

  // Buffer.from is available in Node runtime on Vercel; atob would also work.
  const raw = Buffer.from(body.content, "base64").toString("utf-8");
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new GitHubDataError(
      `Snapshot ${dateIso} did not parse as JSON: ${(e as Error).message}.`,
      { status: resp.status, endpoint },
    );
  }

  // Light shape validation. Don't deep-validate every field; trust the
  // Python writer to produce valid output.
  if (
    typeof parsed !== "object" ||
    parsed === null ||
    !("date" in parsed) ||
    !("students" in parsed) ||
    !Array.isArray((parsed as Snapshot).students)
  ) {
    throw new GitHubDataError(
      `Snapshot ${dateIso} missing required fields (date, students).`,
      { status: resp.status, endpoint },
    );
  }

  const snap = parsed as Snapshot;
  setCache(snapshotCache, dateIso, snap);
  return snap;
}

// ---------------------------------------------------------------------------
// Public: readRange
// ---------------------------------------------------------------------------
/**
 * Read every snapshot whose date falls in [startIso, endIso] inclusive.
 * Missing days are silently skipped. Returns snapshots in date order.
 *
 * This is the workhorse for the dashboard's window selector and mirrors
 * src.history.read_range in the Python backend.
 */
export async function readRange(
  startIso: string,
  endIso: string,
): Promise<Snapshot[]> {
  if (!ISO_DATE_RE.test(startIso) || !ISO_DATE_RE.test(endIso)) {
    throw new GitHubDataError(
      `Invalid range: ${startIso}..${endIso}.`,
      { status: null, endpoint: "(input)" },
    );
  }
  if (startIso > endIso) {
    return [];
  }

  // Use the listing to know which dates to actually fetch — avoids 404
  // round-trips for every gap day.
  const allDates = await listHistoryDates();
  const inRange = allDates.filter((d) => d >= startIso && d <= endIso);

  // Fetch in parallel. Each readSnapshot has its own per-date cache.
  const snapshots = await Promise.all(inRange.map((d) => readSnapshot(d)));

  // Filter out any that came back null (race between listing and fetch).
  const out: Snapshot[] = [];
  for (const s of snapshots) {
    if (s !== null) out.push(s);
  }
  out.sort((a, b) => a.date.localeCompare(b.date));
  return out;
}

// ---------------------------------------------------------------------------
// Test seam: lets unit tests reset module state between runs.
// Not exported in production-facing index; named with __ prefix so it's
// obviously internal.
// ---------------------------------------------------------------------------
export function __resetCacheForTests(): void {
  listingCache.current = null;
  snapshotCache.clear();
}
