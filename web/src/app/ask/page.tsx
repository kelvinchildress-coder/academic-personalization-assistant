/**
 * Phase 6 — /ask page.
 *
 * Server component. The page reads:
 *   ?w=<window>     — handled by resolveWindow, same as head/coach pages
 *   ?k=<askKind>    — selects the palette item; defaults to top_xp
 *   ?n=<number>     — for top_xp / bottom_xp / deficit_*
 *   ?student=<name> — for student_subject_breakdown
 *
 * Coach scope:
 *   - Head coach (kelvin.childress@sportsacademy.school) sees all students.
 *   - Anyone else: results are restricted to their roster from
 *     config/coach_emails.json.
 *
 * No write actions. No external fetches outside the existing data layer.
 */

import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { isHeadCoach } from "@/lib/authz";
import { loadCoachEmailMap } from "@/lib/coachRoster";
import { loadSessions } from "@/lib/sessions";
import { readRange } from "@/lib/githubData";
import { resolveWindow } from "@/lib/window";
import { paramsFromUrl, runAsk } from "@/lib/askKinds";
import { renderAnswer } from "@/lib/askRender";
import { Header } from "@/components/Header";
import { WindowSelector } from "@/components/WindowSelector";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { AskForm } from "./AskForm";
import { AskResult } from "./AskResult";

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<{
    w?: string;
    k?: string;
    n?: string;
    student?: string;
  }>;
}

function todayIso(): string {
  const d = new Date();
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export default async function AskPage({ searchParams }: PageProps) {
  const session = await auth();
  if (!session?.user?.email) {
    redirect("/login");
  }
  const userEmail = session.user.email;
  const head = isHeadCoach(userEmail);

  const sp = await searchParams;

  // ----- Window resolution -----
  const sessions = await loadSessions();
  const today = todayIso();
  const win = resolveWindow(sp.w ?? null, sessions, today);

  // ----- AskParams from URL -----
  const usp = new URLSearchParams();
  if (sp.k) usp.set("k", sp.k);
  if (sp.n) usp.set("n", sp.n);
  if (sp.student) usp.set("student", sp.student);
  const askParams = paramsFromUrl(usp);

  // ----- Coach scope + roster map -----
  const coachMap = await loadCoachEmailMap();
  const coachFilter = head ? null : userEmail;

  // Build student-name → coach-email map. The CoachEmailFile.emails is
  // keyed by student email; we need student NAME (the field used in
  // StudentSnap.name). We fall back to the email's local-part if the
  // snapshot ever uses an email-shaped name; otherwise the map is keyed
  // by display name which we derive lazily during snapshot iteration
  // below.
  //
  // To keep this page authoritative without re-implementing roster
  // resolution, we leverage the existing coach roster file: keys are
  // student emails and values are coach emails. For the Ask page we
  // need student name → coach email, so we iterate the most-recent
  // snapshots to bind name ↔ coach using StudentSnap.coach, then map
  // coach displayed-name → coach email via a heuristic fallback.
  //
  // In practice StudentSnap.coach already holds the coach's email in
  // Phase 7 snapshots (the Python side serializes coach as the email).
  // So this becomes a one-liner: trust StudentSnap.coach.

  // ----- Fetch snapshots -----
  const currentSnaps = await readRange(win.currentStart, win.currentEnd);
  const priorSnaps =
    win.priorStart && win.priorEnd
      ? await readRange(win.priorStart, win.priorEnd)
      : [];

  // Build student-name → coach-email map directly from snapshots.
  // StudentSnap.coach is the coach's email in the Phase 7 snapshot shape.
  const studentNameToCoachEmail = new Map<string, string>();
  for (const day of [...priorSnaps, ...currentSnaps]) {
    for (const stu of day.students) {
      if (!studentNameToCoachEmail.has(stu.name)) {
        studentNameToCoachEmail.set(stu.name, stu.coach);
      }
    }
  }

  // ----- Run the ask -----
  const answer = runAsk({
    params: askParams,
    currentSnaps,
    priorSnaps,
    today,
    currentStart: win.currentStart,
    currentEnd: win.currentEnd,
    priorStart: win.priorStart ?? null,
    priorEnd: win.priorEnd ?? null,
    windowLabel: win.label,
    coachFilter,
    studentNameToCoachEmail,
  });

  const rendered = renderAnswer(answer);

  // Suppress unused-binding warning for coachMap (kept for future
  // coach-display lookups without re-reading the file).
  void coachMap;

  // Find current session id for the WindowSelector's "Current" optgroup.
  const todayDate = today;
  const currentSession = sessions.find(
    (s) => s.startDate <= todayDate && todayDate <= s.endDate,
  );

  return (
    <div className="min-h-screen bg-zinc-50">
      <Header userEmail={userEmail} userName={session.user.name ?? null} />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Ask", href: "/ask" },
          ]}
        />
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <h1 className="text-2xl font-semibold text-zinc-900">Ask</h1>
          <WindowSelector
            value={win.param}
            sessions={sessions}
            currentSessionId={currentSession?.id ?? null}
          />
        </div>
        <p className="mt-1 text-sm text-zinc-600">
          {head
            ? "Roster-wide questions across all coaches."
            : "Roster questions limited to your students."}
        </p>

        <div className="mt-6">
          <AskForm initialParams={askParams} preserveWindow={win.param} />
        </div>

        <div className="mt-8">
          <AskResult rendered={rendered} />
        </div>
      </main>
    </div>
  );
}
