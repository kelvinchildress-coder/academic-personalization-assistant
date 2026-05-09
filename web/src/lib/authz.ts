/**
 * Phase 7 Part 5 — Authorization helpers for coach roster routes.
 *
 * Three principles:
 *   1. The domain allow-list in auth.ts gates SIGN-IN. This module gates
 *      WHICH ROSTER an already-signed-in user can see.
 *   2. Head-coach identity is hardcoded here (parallel to ALLOWED_EMAIL_DOMAINS
 *      in auth.ts). This is an architectural constraint, not a per-deployment
 *      knob -- changing the head coach requires a code commit + deploy.
 *   3. Pure functions only. No imports from githubData, no environment reads,
 *      no React. This module is server-AND-client safe and easy to unit-test.
 */

/**
 * Email addresses that have head-coach privileges (full read access to any
 * coach's roster + the /head overview page).
 *
 * Comparison is case-insensitive and trims surrounding whitespace; we compare
 * against the email as it appears in the OAuth session token.
 */
export const HEAD_COACH_EMAILS = [
  "kelvin.childress@sportsacademy.school",
] as const;

function normalizeEmail(email: string | null | undefined): string {
  if (!email) return "";
  return email.trim().toLowerCase();
}

/**
 * Returns true if the given email is in the hardcoded head-coach allow-list.
 */
export function isHeadCoach(email: string | null | undefined): boolean {
  const norm = normalizeEmail(email);
  if (!norm) return false;
  return HEAD_COACH_EMAILS.some((e) => e.toLowerCase() === norm);
}

/**
 * Returns true if `viewerEmail` is allowed to view the roster belonging to
 * the coach whose email is `targetCoachEmail`.
 *
 * Rules:
 *   - Head coach can view any roster.
 *   - A coach can view their OWN roster (email match, case-insensitive).
 *   - All other combinations: deny.
 *
 * Note: this function takes the TARGET COACH's EMAIL, not the slug. Resolving
 * a URL slug to a coach name and then to a coach email is the caller's job;
 * that mapping lives in slug.ts (name<->slug) and in the snapshot data
 * itself (coach name <-> coach email is currently 1:1 by convention but
 * not enforced by schema -- treat the email as the source of truth).
 */
export function canViewCoachRoster(
  viewerEmail: string | null | undefined,
  targetCoachEmail: string | null | undefined,
): boolean {
  if (isHeadCoach(viewerEmail)) return true;
  const v = normalizeEmail(viewerEmail);
  const t = normalizeEmail(targetCoachEmail);
  if (!v || !t) return false;
  return v === t;
}
