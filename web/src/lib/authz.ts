/**
 * Phase 7 Part 8 — Authz (rewritten).
 *
 * CHANGE FROM PART 5: ownership is no longer slug-of-display-name. It is
 * now email-keyed via config/coach_emails.json (read through coachRoster.ts).
 * This closes the display-name-spoof gap: a coach who renames their Google
 * account cannot impersonate another coach, because we match canonical
 * email -> canonical coach name -> compare against the requested coachId
 * slug.
 *
 * Q8-7 (A): if a signed-in user's email is not in the email map and is not
 * the head coach, they are NOT signed out — they land on /no-roster with a
 * friendly explanation.
 *
 * Public surface (compatible with Part 5 callers):
 *   - HEAD_COACH_EMAILS: readonly string[]
 *   - isHeadCoach(email): boolean
 *   - canViewCoach(session, coachId): Promise<boolean>   (signature compatible)
 *
 * New in Part 8:
 *   - getRoleForEmail(email): Promise<Role>
 *   - coachIdForEmail(email): Promise<string | null>
 *   - requireCoachOrRedirect(session, coachId): Promise<{ ok: true; coachName: string }
 *                                                       | { ok: false; redirect: string }>
 */

import "server-only";
import { resolveCoachByEmail } from "./coachRoster";
import { slugify } from "./slug";
import type { Session as NextAuthSession } from "next-auth";

/** Hardcoded head-coach emails. Edit + redeploy to add/change. */
export const HEAD_COACH_EMAILS: readonly string[] = [
  "kelvin.childress@sportsacademy.school",
];

export type Role = "head_coach" | "coach" | "no_roster";

/** Pure check: is the email a head coach? Case-insensitive. */
export function isHeadCoach(email: string | null | undefined): boolean {
  if (!email) return false;
  const lc = email.toLowerCase();
  return HEAD_COACH_EMAILS.some((h) => h.toLowerCase() === lc);
}

/** Resolve role for a signed-in email. */
export async function getRoleForEmail(
  email: string | null | undefined
): Promise<Role> {
  if (!email) return "no_roster";
  if (isHeadCoach(email)) return "head_coach";
  const coachName = await resolveCoachByEmail(email);
  return coachName ? "coach" : "no_roster";
}

/** Return the canonical coachId slug for a signed-in coach email, or null. */
export async function coachIdForEmail(
  email: string | null | undefined
): Promise<string | null> {
  const coachName = await resolveCoachByEmail(email);
  if (!coachName) return null;
  return slugify(coachName);
}

/**
 * Compatible-signature ownership check. Returns true if the session user
 * is the head coach (sees any roster) OR the email-mapped coach matches
 * the requested coachId slug.
 */
export async function canViewCoach(
  session: NextAuthSession | null,
  coachId: string
): Promise<boolean> {
  const email = session?.user?.email ?? null;
  if (!email) return false;
  if (isHeadCoach(email)) return true;
  const ownId = await coachIdForEmail(email);
  return ownId !== null && ownId === coachId;
}

/**
 * Page-level guard. Returns either { ok: true, coachName } if the request
 * is allowed (head coach OR email-mapped owner of coachId), or
 * { ok: false, redirect } with a destination path.
 *
 * Redirect targets:
 *   - "/login"        unauthenticated
 *   - "/no-roster"    authenticated but email not in map and not head coach
 *   - "/coach/<own>"  authenticated coach trying to view someone else's roster
 *
 * The caller should call redirect(result.redirect) from a server component.
 */
export async function requireCoachOrRedirect(
  session: NextAuthSession | null,
  coachId: string
): Promise<{ ok: true; coachName: string } | { ok: false; redirect: string }> {
  const email = session?.user?.email ?? null;
  if (!email) return { ok: false, redirect: "/login" };

  if (isHeadCoach(email)) {
    // Head coach can view anyone; we still need the canonical coachName for
    // breadcrumb/header. Best effort: reverse-lookup is not strictly required
    // here because the page itself will load the coach by id. Return empty
    // string and let the page resolve the display name from coaches.json.
    return { ok: true, coachName: "" };
  }

  const coachName = await resolveCoachByEmail(email);
  if (!coachName) return { ok: false, redirect: "/no-roster" };

  const ownId = slugify(coachName);
  if (ownId !== coachId) return { ok: false, redirect: `/coach/${ownId}` };

  return { ok: true, coachName };
}
