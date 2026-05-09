"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { ALL_WINDOWS, parseWindowParam, type ResolvedWindow } from "@/lib/window";

/**
 * Phase 7 Part 6 — Window selector.
 *
 * Three-button toggle that updates the URL's `?window=...` query param.
 * Server components on each page parse this param via parseWindowParam to
 * decide how many days of history to fetch.
 *
 * Why a client component? Because changing the window must update the URL
 * without a full page navigation flicker. We use Next.js's app-router
 * client-side navigation via useRouter().push().
 */
export default function WindowSelector() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current: ResolvedWindow = parseWindowParam(
    searchParams.get("window"),
  );

  function selectWindow(key: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (key === "30d") {
      next.delete("window"); // 30d is the default; keep URLs clean.
    } else {
      next.set("window", key);
    }
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  }

  return (
    <div
      role="group"
      aria-label="Time window"
      className="inline-flex overflow-hidden rounded border border-gray-300 text-xs"
    >
      {ALL_WINDOWS.map((w) => {
        const active = w.key === current.key;
        return (
          <button
            key={w.key}
            type="button"
            onClick={() => selectWindow(w.key)}
            aria-pressed={active}
            className={
              "px-3 py-1.5 transition " +
              (active
                ? "bg-gray-900 text-white"
                : "bg-white text-gray-700 hover:bg-gray-50")
            }
          >
            {w.label}
          </button>
        );
      })}
    </div>
  );
}
