/**
 * Phase 7 Part 5 — Coach name <-> URL slug helpers.
 *
 * We use display-name slugs in URLs (e.g., "lisa-c-willis") rather than
 * raw email addresses so:
 *   - URLs are clean and don't leak PII into browser history / referrers
 *   - URLs are bookmark-friendly and shareable in Slack DMs
 *   - The Phase 4 normalization "Lisa Willis" -> "Lisa C Willis" carries
 *     forward into routing without extra plumbing
 *
 * Slugs are derived from the coach `name` field on each StudentSnap, NOT
 * from the email. Authorization (who can view which slug) is handled
 * separately in authz.ts using the email from the session.
 */

/**
 * Convert a coach display name to a lowercase, hyphen-separated URL slug.
 *
 * Rules:
 *   - Unicode-normalized (NFKD) and stripped of combining marks so accented
 *     characters become their ASCII equivalents.
 *   - Lowercased.
 *   - All runs of non-alphanumeric characters become a single hyphen.
 *   - Leading and trailing hyphens are trimmed.
 *   - Empty input or input that normalizes to an empty string returns "".
 *
 * Examples:
 *   "Lisa C Willis"     -> "lisa-c-willis"
 *   "  José Núñez  "    -> "jose-nunez"
 *   "O'Connor, Ryan"    -> "o-connor-ryan"
 *   ""                  -> ""
 */
export function slugifyName(name: string | null | undefined): string {
  if (!name) return "";
  const ascii = name.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
  const slug = ascii
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug;
}

/**
 * Alias export. Several Phase 7 / Phase 8 call sites import `slugify`
 * from this module (authz.ts, student detail page). Keeping both names
 * exported lets old call sites and the canonical name co-exist without
 * a sweeping rename.
 */
export const slugify = slugifyName;

/**
 * Build a bidirectional index of coach names <-> slugs from a list of
 * student snapshots.
 *
 * Returns an object with:
 *   - bySlug: Map<slug, canonical coach name>
 *   - byName: Map<canonical coach name, slug>
 *
 * "Canonical" means the first-seen spelling for that slug. If two coaches
 * happen to slug-collide (e.g., "Lisa Willis" and "Lisa-Willis" both ->
 * "lisa-willis"), the first one wins and a warning is logged in dev.
 *
 * The student-list shape is intentionally narrow (just `{ coach: string }`)
 * so this helper can be called with either StudentSnap[] from a Snapshot
 * or any other source that exposes a coach name.
 */
export function buildCoachIndex(
  students: ReadonlyArray<{ coach: string }>,
): {
  bySlug: Map<string, string>;
  byName: Map<string, string>;
} {
  const bySlug = new Map<string, string>();
  const byName = new Map<string, string>();
  for (const s of students) {
    const name = s.coach;
    if (!name) continue;
    if (byName.has(name)) continue;
    const slug = slugifyName(name);
    if (!slug) continue;
    if (bySlug.has(slug) && bySlug.get(slug) !== name) {
      // Slug collision between two distinct coach names. First-seen wins;
      // the loser is unreachable via slug-based routing. This is
      // exceedingly unlikely with real coach names but worth surfacing.
      if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.warn(
          `[slug] collision: "${name}" -> "${slug}" already taken by "${bySlug.get(slug)}"`,
        );
      }
      continue;
    }
    bySlug.set(slug, name);
    byName.set(name, slug);
  }
  return { bySlug, byName };
}
