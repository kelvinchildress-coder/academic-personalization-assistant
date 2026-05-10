/**
 * Phase 7 Part 8 — Breadcrumbs.
 *
 * Q8-3 (A): full path, e.g.:
 *   Home › Head overview › Ella Alexander › Lucy Wilkinson
 *
 * Pure server component. The parent (Header) computes the trail and
 * passes it in. Each crumb is { label, href? }; the last crumb is
 * rendered as plain text without a link.
 */

import Link from "next/link";

export interface Crumb {
  label: string;
  href?: string;
}

export function Breadcrumbs({ trail }: { trail: Crumb[] }) {
  if (trail.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-zinc-500">
      <ol className="flex flex-wrap items-center gap-1.5">
        {trail.map((c, i) => {
          const isLast = i === trail.length - 1;
          return (
            <li key={i} className="flex items-center gap-1.5">
              {i > 0 && (
                <span aria-hidden className="text-zinc-300">›</span>
              )}
              {isLast || !c.href ? (
                <span
                  className={isLast ? "text-zinc-900 font-medium" : "text-zinc-500"}
                  aria-current={isLast ? "page" : undefined}
                >
                  {c.label}
                </span>
              ) : (
                <Link
                  href={c.href}
                  className="text-zinc-500 hover:text-zinc-900 hover:underline"
                >
                  {c.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
