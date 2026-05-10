/**
 * Phase 7 Part 8 — Persistent site header.
 *
 * Server component that renders on every authed page. Layout:
 *   [ Brand ] ──── [ Breadcrumb trail ] ────────────── [ UserMenu ]
 *
 * Visibility: hidden on /login. Sign-in state checked via auth() from
 * web/src/auth.ts. If unauthenticated (e.g. server-rendered before
 * middleware redirect), shows a minimal brand-only bar.
 *
 * Q8-3 (A): full breadcrumb trail. Q8-4 (A): avatar + name + role badge
 * + dropdown.
 */

import Link from "next/link";
import { auth } from "@/auth";
import { Breadcrumbs, type Crumb } from "./Breadcrumbs";
import { UserMenu } from "./UserMenu";
import { isHeadCoach } from "@/lib/authz";
import { resolveCoachByEmail } from "@/lib/coachRoster";

interface Props {
  trail?: Crumb[];
}

export async function Header({ trail = [] }: Props) {
  const session = await auth();

  // Determine role for the UserMenu badge.
  let role: "head_coach" | "coach" | "no_roster" = "no_roster";
  if (session?.user?.email) {
    if (isHeadCoach(session.user.email)) {
      role = "head_coach";
    } else {
      const coachName = await resolveCoachByEmail(session.user.email);
      role = coachName ? "coach" : "no_roster";
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/75">
      <div className="mx-auto max-w-7xl px-3 sm:px-6 py-2 flex items-center gap-3 sm:gap-6 flex-wrap">
        <Link
          href="/"
          className="flex items-center gap-2 text-sm font-semibold text-zinc-900 hover:text-zinc-700"
        >
          <span
            aria-hidden
            className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-zinc-900 text-white text-xs"
          >
            TSA
          </span>
          <span className="hidden sm:inline">Academic Personalization</span>
        </Link>

        <div className="flex-1 min-w-0">
          <Breadcrumbs trail={trail} />
        </div>

        {session?.user ? (
          <UserMenu
            name={session.user.name ?? session.user.email ?? "User"}
            email={session.user.email ?? ""}
            image={session.user.image ?? null}
            role={role}
          />
        ) : null}
      </div>
    </header>
  );
}
