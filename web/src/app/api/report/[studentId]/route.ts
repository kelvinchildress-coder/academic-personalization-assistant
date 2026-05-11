/**
 * Phase 5 — Student report PDF endpoint (Cycle I — PDF streaming).
 *
 * GET /api/report/<studentId>?scope=eoq|eoy
 *
 * Authorization:
 *   - Must be signed in. Else 401.
 *   - Head coach sees any student. Else the student's coach email must
 *     equal the signed-in email. Else 403.
 *
 * Scope:
 *   - "eoq" (default): current session window via findCurrentSession;
 *     falls back to "30d" if no current session.
 *   - "eoy": last 365 days.
 *
 * Response:
 *   - 200 application/pdf streaming download.
 *   - 401/403/404 application/json.
 *
 * Q-Phase5-5: ephemeral — nothing is stored.
 * Q-Phase5-10: no logging of generation events.
 *
 * Runtime: nodejs (required by @react-pdf/renderer which uses Node APIs).
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { Readable } from "node:stream";
import React from "react";
import { renderToStream } from "@react-pdf/renderer";

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
import { StudentReportPDF } from "@/components/report/StudentReportPDF";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function todayIso(): string {
  const d = new Date();
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function parseScope(raw: string | null): ReportScope {
  if (raw === "eoy") return "eoy";
  return "eoq";
}

interface RouteContext {
  params: { studentId: string };
}

export async function GET(req: NextRequest, ctx: RouteContext) {
  const session = await auth();
  const email = session?.user?.email ?? null;
  if (!email) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const head = isHeadCoach(email);

  const url = new URL(req.url);
  const scope = parseScope(url.searchParams.get("scope"));

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

  const currentSnaps = await readRange(win.currentStart, win.currentEnd);
  const priorSnaps =
    win.priorStart && win.priorEnd
      ? await readRange(win.priorStart, win.priorEnd)
      : [];

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

  if (!head) {
    const coachName = await resolveCoachByEmail(email);
    if (!coachName) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
    if (studentCoach.toLowerCase() !== email.toLowerCase()) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
  }

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

  const filename = reportFilename(studentId, scope, today);

  // Render the PDF to a Node Readable stream, then convert to a web
  // ReadableStream so we can hand it back as Response.body. Node 18+
  // ships Readable.toWeb which produces exactly the shape Response wants.
  const nodeStream = await renderToStream(
    React.createElement(StudentReportPDF, { payload }),
  );
  const webStream = Readable.toWeb(nodeStream as Readable) as ReadableStream;

  return new Response(webStream, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store, no-cache, must-revalidate",
      "X-Report-Filename": filename,
    },
  });
}
