"use client";

/**
 * Phase 7 Part 8 — UserMenu (top-right identity widget).
 *
 * Shows the signed-in user's avatar, display name, role badge, and a
 * dropdown with email + sign-out. Q8-4 (A): full widget with avatar +
 * name + role + email-on-expand + sign-out.
 *
 * Note: image/avatar comes from Google profile via session.user.image.
 * If absent, falls back to initials.
 */

import { useState } from "react";
import { signOut } from "next-auth/react";

interface Props {
  name: string;
  email: string;
  image: string | null;
  role: "head_coach" | "coach" | "no_roster";
}

const ROLE_LABEL: Record<Props["role"], string> = {
  head_coach: "Head Coach",
  coach: "Coach",
  no_roster: "No roster",
};

const ROLE_BADGE_CLASS: Record<Props["role"], string> = {
  head_coach: "bg-amber-100 text-amber-900 ring-amber-300",
  coach: "bg-sky-100 text-sky-900 ring-sky-300",
  no_roster: "bg-zinc-100 text-zinc-700 ring-zinc-300",
};

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function UserMenu({ name, email, image, role }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md border border-zinc-200 bg-white px-2 py-1 text-sm hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-sky-400"
      >
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={image}
            alt=""
            className="h-7 w-7 rounded-full"
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-zinc-200 text-xs font-semibold text-zinc-700">
            {initialsOf(name)}
          </span>
        )}
        <span className="hidden sm:block text-zinc-900">{name}</span>
        <span
          className={`hidden sm:inline rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${ROLE_BADGE_CLASS[role]}`}
        >
          {ROLE_LABEL[role]}
        </span>
        <span aria-hidden className="text-zinc-400">▾</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-1 w-64 rounded-md border border-zinc-200 bg-white shadow-lg ring-1 ring-black/5 z-50"
        >
          <div className="px-3 py-2 text-sm text-zinc-700 border-b border-zinc-100">
            <div className="font-medium text-zinc-900">{name}</div>
            <div className="text-xs text-zinc-500 break-all">{email}</div>
            <div className="mt-1">
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${ROLE_BADGE_CLASS[role]}`}
              >
                {ROLE_LABEL[role]}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/" })}
            className="block w-full px-3 py-2 text-left text-sm text-zinc-800 hover:bg-zinc-50"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
