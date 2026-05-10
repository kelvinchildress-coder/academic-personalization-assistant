/**
 * Phase 6 — Ask result table renderer.
 *
 * Server component. Pure presentation of a RenderedTable from
 * lib/askRender. No data fetching here; the page has already computed
 * everything.
 */

import type { RenderedTable } from "@/lib/askRender";

interface Props {
  rendered: RenderedTable;
}

export function AskResult({ rendered }: Props) {
  const { title, subtitle, columns, rows, emptyNotice } = rendered;

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <header className="border-b border-zinc-200 px-4 py-3">
        <h2 className="text-lg font-semibold text-zinc-900">{title}</h2>
        <p className="mt-0.5 text-xs text-zinc-500">{subtitle}</p>
      </header>

      {rows.length === 0 ? (
        <div className="px-4 py-6 text-sm text-zinc-600">{emptyNotice}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-50">
              <tr>
                {columns.map((c) => (
                  <th
                    key={c.id}
                    scope="col"
                    className={
                      "px-3 py-2 font-medium text-zinc-700 " +
                      (c.align === "right" ? "text-right" : "text-left")
                    }
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((r, i) => (
                <tr key={i} className="hover:bg-zinc-50">
                  {r.map((cell, j) => (
                    <td
                      key={j}
                      className={
                        "whitespace-nowrap px-3 py-2 text-zinc-800 " +
                        (columns[j]?.align === "right" ? "text-right" : "text-left")
                      }
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
