/**
 * Phase 5 — Student report PDF endpoint (Cycle H stub).
 *
 * GET /api/report/<studentId>?scope=eoq|eoy
 *
 * Authorization:
 *   - Must be signed in (NextAuth session). Else 401.
 *   - Head coach sees any student. Else the requested student must belong
 *     to the signed-in coach's roster. Else 403.
 *
 * Scope:
 *   - "eoq" (default): the current session window from data/sessions.json,
 *     resolved via resolveWindow. If no current session, falls back to 30d.
 *   - "eoy": last 365 days.
 *
 * Response:
 *   - 200 application/pdf with Content-Disposition: attachment;
 *     filename="<studentSlug>_<scope>_<dateIso>.pdf"        (Cycle I)
 *   - 401 application/json {"error":"unauthorized"}
 *   - 403 application/json {"error":"forbidden"}
 *   - 404 application/json {"error":"student not found in scope"}
 *   - 503 application/json {"error":"report rendering not yet enabled"}
 *                                                          (Cycle H stub)
 *
 * Per Phase 5 Design Brief Q-Phase5-5: ephemeral. Nothing is stored.
 * Per Q-Phase5-10: no logging of generation events.
 *
 * Cycle H delivers: full auth + scope + data-assembly path, returning a
 * structured 503 in the final step so `main` keeps building cleanly.
 * Cycle I replaces only the final stub block with the actual PDF stream.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { auth } from "@/auth";
import { isHeadCoach } from "@/lib/authz";
import { resolveCoachByEmail } from "@/lib/coachRoster";
import { slugify } from "@/lib/slug";
import { getSessions, findCurrentSession } from "@/lib/sessions";
import { resolveWindow } from "@/lib/window";
import { readRange } from "@/lib/githubData";
import {
  buildReportPayload,
  reportFilename,
  REPORT_SCOPE_LABEL,
  type ReportScope,
} from "@/lib/reportData";

export const dynamic = "force-dynamic";

function todayIso(): string {
  const d = new Date();
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function parseScope(raw: string | null): ReportScope {
  if (raw === "eoy") return "eoy";
  return "eoq"; // default + any unknown value
}

interface RouteContext {
  params: { studentId: string };
}

export async function GET(req: NextRequest, ctx: RouteContext) {
  // ----- Auth -----
  const session = await auth();
  const email = session?.user?.email ?? null;
  if (!email) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const head = isHeadCoach(email);

  // ----- Scope -----
  const url = new URL(req.url);
  const scope = parseScope(url.searchParams.get("scope"));

  // ----- Window resolution -----
  const sessions = await getSessions();
  const today = todayIso();

  let windowParam: string;
  if (scope === "eoy") {
    windowParam = "year";
  } else {
    const current = findCurrentSession(sessions, today);
    windowParam = current?.id ?? "30d";
  }
  const win = resolveWindow(windowParam, sessions, today);

  // ----- Fetch snapshots -----
  const currentSnaps = await readRange(win.currentStart, win.currentEnd);
  const priorSnaps =
    win.priorStart && win.priorEnd
      ? await readRange(win.priorStart, win.priorEnd)
      : [];

  // ----- Resolve studentId slug to a real student name -----
  const studentId = ctx.params.studentId;
  let studentName: string | null = null;
  let studentCoach: string | null = null;
  for (const day of [...priorSnaps, ...currentSnaps]) {
    for (const stu of day.students) {
      if (slugify(stu.name) === studentId) {
        studentName = stu.name;
        studentCoach = stu.coach;
        break;
      }
    }
    if (studentName) break;
  }
  if (!studentName || !studentCoach) {
    return NextResponse.json(
      { error: "student not found in scope" },
      { status: 404 },
    );
  }

  // ----- Authorization: head coach passes; otherwise email must map to a
  //                     coach AND that coach must own this student. -----
  if (!head) {
    const coachName = await resolveCoachByEmail(email);
    if (!coachName) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
    // StudentSnap.coach is the coach's email in Phase 7 snapshots.
    if (studentCoach.toLowerCase() !== email.toLowerCase()) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
  }

  // ----- Assemble the report payload (pure). -----
  const payload = buildReportPayload({
    studentName,
    schoolName: "Texas Sports Academy",
    scope,
    scopeLabel: REPORT_SCOPE_LABEL[scope],
    windowLabel: win.label,
    generatedDateIso: today,
    currentSnaps,
    priorSnaps,
    currentStart: win.currentStart,
    currentEnd: win.currentEnd,
    priorStart: win.priorStart ?? null,
    priorEnd: win.priorEnd ?? null,
  });
  if (!payload) {
    return NextResponse.json(
      { error: "student not found in scope" },
      { status: 404 },
    );
  }

  // ----- Filename (used by Cycle I when the PDF stream is wired up). -----
  const filename = reportFilename(studentId, scope, today);

  // ----- Cycle H stub: return a structured 503 with the resolved metadata.
  //       Cycle I replaces this block with the @react-pdf/renderer stream
  //       (renderToStream(<StudentReportPDF payload={payload}/>) piped
  //       through a Response with Content-Type: application/pdf and the
  //       Content-Disposition header below).
  return NextResponse.json(
    {
      error: "report rendering not yet enabled",
      detail: "Cycle I will enable PDF generation; data path is verified.",
      filename,
      scope: payload.scope,
      windowLabel: payload.windowLabel,
      summaryLine: payload.summaryLine,
    },
    {
      status: 503,
      headers: {
        // Hint to Cycle I: this is the header it'll emit alongside the PDF.
        "X-Report-Filename": filename,
      },
    },
  );
}
