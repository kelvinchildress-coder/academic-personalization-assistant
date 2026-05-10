/**
 * Phase 7 Part 8 — Coach email-to-name mapping (closes display-name-spoof).
 *
 * Reads config/coach_emails.json via the GitHub data layer. The map is
 * keyed by display name (which matches config/coaches.json keys) and
 * valued by canonical email. The dashboard's authz layer uses this to
 * verify a signed-in user's email actually belongs to the coach whose
 * roster URL they're requesting — independent of the user's Google
 * display name (which they can change).
 */

import "server-only";
import type { CoachEmailFile } from "./types";
import { fetchJson } from "./githubData";

/**
 * Returns a Map keyed by lowercased email, valued by display name.
 * This is the lookup used by authz: given session.user.email, find
 * the canonical coach display name (or null if not on the roster).
 */
export async function getEmailToCoachMap(): Promise<Map<string, string>> {
  const raw = await fetchJson<CoachEmailFile>("config/coach_emails.json").catch(
    () => null
  );
  const map = new Map<string, string>();
  if (!raw || !raw.emails) return map;
  for (const [name, email] of Object.entries(raw.emails)) {
    if (typeof email !== "string" || email.length === 0) continue;
    map.set(email.toLowerCase(), name);
  }
  return map;
}

/**
 * Returns a Map keyed by display name, valued by lowercased email.
 * Used for the head-coach view to display each coach's email next to
 * their name, and for outbound links.
 */
export async function getCoachToEmailMap(): Promise<Map<string, string>> {
  const raw = await fetchJson<CoachEmailFile>("config/coach_emails.json").catch(
    () => null
  );
  const map = new Map<string, string>();
  if (!raw || !raw.emails) return map;
  for (const [name, email] of Object.entries(raw.emails)) {
    if (typeof email !== "string" || email.length === 0) continue;
    map.set(name, email.toLowerCase());
  }
  return map;
}

/**
 * Resolve a signed-in email to a coach display name. Returns null if
 * the email is not in the roster. The `email` arg is matched
 * case-insensitively.
 */
export async function resolveCoachByEmail(
  email: string | null | undefined
): Promise<string | null> {
  if (!email) return null;
  const map = await getEmailToCoachMap();
  return map.get(email.toLowerCase()) ?? null;
}
