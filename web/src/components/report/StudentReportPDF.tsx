/**
 * Phase 5 — StudentReportPDF.
 *
 * @react-pdf/renderer document for the student academic summary report.
 * Pure presentational component: takes a ReportPayload (assembled by
 * reportData.ts) and renders the PDF. No fetching, no I/O.
 *
 * Layout per Phase 5 Design Brief:
 *   Q-Phase5-6: text cover — school name, student, coach, scope, date,
 *               one-line summary.
 *   Q-Phase5-7 (A minus iv): per-subject XP table + concern summary +
 *               window-vs-window delta. NO coach-notes section.
 *   Q-Phase5-9: header brand + footer "Page N of M · Generated YYYY-MM-DD
 *               · Confidential — for school and family use only".
 *
 * Fonts: uses built-in Helvetica (no font registration needed).
 */
import {
  Document,
  Page,
  View,
  Text,
  StyleSheet,
} from "@react-pdf/renderer";
import type { ReportPayload } from "@/lib/reportData";

const styles = StyleSheet.create({
  page: {
    paddingTop: 48,
    paddingBottom: 56,
    paddingHorizontal: 48,
    fontFamily: "Helvetica",
    fontSize: 10,
    color: "#111827",
  },
  brandRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#d4d4d8",
  },
  brand: {
    fontSize: 11,
    fontFamily: "Helvetica-Bold",
    color: "#18181b",
  },
  brandRight: {
    fontSize: 9,
    color: "#52525b",
  },
  coverBlock: {
    marginTop: 8,
    marginBottom: 24,
  },
  schoolName: {
    fontSize: 12,
    color: "#52525b",
    marginBottom: 4,
  },
  studentName: {
    fontSize: 22,
    fontFamily: "Helvetica-Bold",
    color: "#0f172a",
    marginBottom: 6,
  },
  coverMeta: {
    fontSize: 10,
    color: "#27272a",
    marginBottom: 2,
  },
  summaryLine: {
    marginTop: 10,
    fontSize: 11,
    fontFamily: "Helvetica-Oblique",
    color: "#1f2937",
    lineHeight: 1.4,
  },
  sectionTitle: {
    fontSize: 12,
    fontFamily: "Helvetica-Bold",
    color: "#0f172a",
    marginTop: 16,
    marginBottom: 8,
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: "#f4f4f5",
    paddingVertical: 5,
    paddingHorizontal: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#d4d4d8",
  },
  tableRow: {
    flexDirection: "row",
    paddingVertical: 4,
    paddingHorizontal: 6,
    borderBottomWidth: 0.5,
    borderBottomColor: "#e4e4e7",
  },
  thSubject: { width: "40%", fontFamily: "Helvetica-Bold", fontSize: 9 },
  thNum: { width: "15%", fontFamily: "Helvetica-Bold", fontSize: 9, textAlign: "right" },
  tdSubject: { width: "40%", fontSize: 10 },
  tdNum: { width: "15%", fontSize: 10, textAlign: "right" },
  daysObserved: {
    fontSize: 8,
    color: "#71717a",
    marginTop: 2,
  },
  concernRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 4,
  },
  concernDot: {
    fontSize: 10,
    color: "#b45309",
    marginRight: 6,
  },
  concernLabel: {
    fontSize: 10,
    color: "#1f2937",
  },
  noConcerns: {
    fontSize: 10,
    color: "#15803d",
    fontFamily: "Helvetica-Oblique",
  },
  deltaTable: {
    marginTop: 4,
  },
  deltaRow: {
    flexDirection: "row",
    paddingVertical: 3,
  },
  deltaLabel: {
    width: "60%",
    fontSize: 10,
    color: "#27272a",
  },
  deltaValue: {
    width: "40%",
    fontSize: 10,
    fontFamily: "Helvetica-Bold",
    color: "#0f172a",
    textAlign: "right",
  },
  deltaPos: {
    color: "#b91c1c",
  },
  deltaNeg: {
    color: "#15803d",
  },
  emptySection: {
    fontSize: 10,
    color: "#71717a",
    fontFamily: "Helvetica-Oblique",
  },
  footer: {
    position: "absolute",
    bottom: 24,
    left: 48,
    right: 48,
    fontSize: 8,
    color: "#71717a",
    textAlign: "center",
  },
});

function formatNumber(n: number, digits: number = 0): string {
  return n.toFixed(digits);
}

function formatSignedNumber(n: number, digits: number = 0): string {
  if (n > 0) return `+${n.toFixed(digits)}`;
  return n.toFixed(digits);
}

interface Props {
  payload: ReportPayload;
}

export function StudentReportPDF({ payload }: Props) {
  const hasSubjects = payload.subjects.length > 0;
  const hasConcerns = payload.concerns.length > 0;
  const hasDelta = payload.delta.priorDeficit !== null;

  return (
    <Document
      title={`${payload.studentName} — ${payload.scopeLabel}`}
      author={payload.schoolName}
      creator={payload.schoolName}
      producer="Academic Personalization Assistant"
    >
      <Page size="LETTER" style={styles.page} wrap>
        {/* Brand header */}
        <View style={styles.brandRow} fixed>
          <Text style={styles.brand}>
            Texas Sports Academy — Academic Summary
          </Text>
          <Text style={styles.brandRight}>{payload.scopeLabel}</Text>
        </View>

        {/* Cover block */}
        <View style={styles.coverBlock}>
          <Text style={styles.schoolName}>{payload.schoolName}</Text>
          <Text style={styles.studentName}>{payload.studentName}</Text>
          <Text style={styles.coverMeta}>Coach: {payload.coachName}</Text>
          <Text style={styles.coverMeta}>
            Scope: {payload.scopeLabel} ({payload.windowLabel})
          </Text>
          <Text style={styles.coverMeta}>
            Window: {payload.delta.currentStart} to {payload.delta.currentEnd}
          </Text>
          <Text style={styles.coverMeta}>
            Generated: {payload.generatedDateIso}
          </Text>
          <Text style={styles.summaryLine}>{payload.summaryLine}</Text>
        </View>

        {/* Subject targets table */}
        <Text style={styles.sectionTitle}>Subject targets</Text>
        {hasSubjects ? (
          <View>
            <View style={styles.tableHeader}>
              <Text style={styles.thSubject}>Subject</Text>
              <Text style={styles.thNum}>Target/day</Text>
              <Text style={styles.thNum}>Actual/day</Text>
              <Text style={styles.thNum}>Delta</Text>
              <Text style={styles.thNum}>Days</Text>
            </View>
            {payload.subjects.map((s) => (
              <View key={s.subject} style={styles.tableRow}>
                <Text style={styles.tdSubject}>{s.subject}</Text>
                <Text style={styles.tdNum}>
                  {formatNumber(s.avgTargetPerDay, 1)}
                </Text>
                <Text style={styles.tdNum}>
                  {formatNumber(s.avgActualPerDay, 1)}
                </Text>
                <Text
                  style={[
                    styles.tdNum,
                    s.delta >= 0 ? styles.deltaNeg : styles.deltaPos,
                  ]}
                >
                  {formatSignedNumber(s.delta, 1)}
                </Text>
                <Text style={styles.tdNum}>{s.daysObserved}</Text>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.emptySection}>
            No per-subject snapshots available in this scope.
          </Text>
        )}

        {/* Active concerns */}
        <Text style={styles.sectionTitle}>Active concerns</Text>
        {hasConcerns ? (
          <View>
            {payload.concerns.map((c) => (
              <View key={c.code} style={styles.concernRow}>
                <Text style={styles.concernDot}>•</Text>
                <Text style={styles.concernLabel}>{c.label}</Text>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.noConcerns}>
            No active concerns in this scope.
          </Text>
        )}

        {/* Window-vs-window delta */}
        <Text style={styles.sectionTitle}>Deficit trend</Text>
        <View style={styles.deltaTable}>
          <View style={styles.deltaRow}>
            <Text style={styles.deltaLabel}>Current-window deficit (XP)</Text>
            <Text style={styles.deltaValue}>
              {formatNumber(payload.delta.currentDeficit, 0)}
            </Text>
          </View>
          {hasDelta ? (
            <>
              <View style={styles.deltaRow}>
                <Text style={styles.deltaLabel}>
                  Prior-window deficit (XP) — {payload.delta.priorStart} to{" "}
                  {payload.delta.priorEnd}
                </Text>
                <Text style={styles.deltaValue}>
                  {formatNumber(payload.delta.priorDeficit ?? 0, 0)}
                </Text>
              </View>
              <View style={styles.deltaRow}>
                <Text style={styles.deltaLabel}>Change vs prior</Text>
                <Text
                  style={[
                    styles.deltaValue,
                    (payload.delta.delta ?? 0) > 0
                      ? styles.deltaPos
                      : styles.deltaNeg,
                  ]}
                >
                  {formatSignedNumber(payload.delta.delta ?? 0, 0)} XP
                </Text>
              </View>
            </>
          ) : (
            <View style={styles.deltaRow}>
              <Text style={styles.deltaLabel}>
                No prior-window data available for comparison.
              </Text>
              <Text style={styles.deltaValue}>—</Text>
            </View>
          )}
        </View>

        {/* Coverage diagnostics */}
        <Text style={styles.daysObserved}>
          Based on {payload.daysPresent} of {payload.daysInCurrentWindow} days
          observed in the current window.
        </Text>

        {/* Footer (fixed on every page) */}
        <Text
          style={styles.footer}
          fixed
          render={({ pageNumber, totalPages }) =>
            `Page ${pageNumber} of ${totalPages} · Generated ${payload.generatedDateIso} · Confidential — for school and family use only`
          }
        />
      </Page>
    </Document>
  );
}
