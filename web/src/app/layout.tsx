/**
 * Phase 7 Part 8 — Root layout.
 *
 * Wraps every authed page in the persistent Header. The Header itself
 * is rendered conditionally — login page passes its own minimal layout.
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Academic Personalization Assistant",
  description: "Texas Sports Academy — coach dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-zinc-50 text-zinc-900 antialiased">
        {children}
      </body>
    </html>
  );
}
