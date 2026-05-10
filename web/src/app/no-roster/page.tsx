/**
 * Phase 7 Part 8 — No-roster fallback page (Q8-7 A).
 *
 * Reached when a signed-in user's email is not in config/coach_emails.json
 * and is not the head coach. Rather than redirect-loop or hard-fail,
 * we show a friendly explanation and contact info.
 */

import { auth } from "@/auth";
import { Header } from "@/components/Header";
import { redirect } from "next/navigation";
import { isHeadCoach } from "@/lib/authz";
import { resolveCoachByEmail } from "@/lib/coachRoster";
import { slugify } from "@/lib/slug";

export const dynamic = "force-dynamic";

export default async function NoRosterPage() {
  const session = await auth();
  if (!session?.user?.email) redirect("/login");

  // If the user actually IS a coach or head coach, send them home.
  if (isHeadCoach(session.user.email)) redirect("/head");
  const coachName = await resolveCoachByEmail(session.user.email);
  if (coachName) redirect(`/coach/${slugify(coachName)}`);

  return (
    <>
      <Header trail={[{ label: "Home", href: "/" }, { label: "No roster" }]} />
      <main className="mx-auto max-w-2xl px-4 py-12">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
          <h1 className="text-lg font-semibold text-amber-900">
            No roster assigned
          </h1>
          <p className="mt-2 text-sm text-amber-900/90">
            You&apos;re signed in as{" "}
            <span className="font-mono">{session.user.email}</span>, but this
            email isn&apos;t mapped to a coach in the current roster.
          </p>
          <p className="mt-3 text-sm text-amber-900/90">
            If you&apos;re a coach who should have access, please contact the
            head coach to be added to{" "}
            <span className="font-mono">config/coach_emails.json</span>.
          </p>
          <p className="mt-3 text-sm text-amber-900/90">
            If you signed in with the wrong account, sign out from the menu
            in the top-right and try again with your{" "}
            <span className="font-mono">@sportsacademy.school</span> address.
          </p>
        </div>
      </main>
    </>
  );
}
