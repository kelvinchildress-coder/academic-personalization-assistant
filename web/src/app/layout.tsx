import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TSA Academic Dashboard",
  description:
    "Texas Sports Academy — academic personalization dashboard for coaches.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
