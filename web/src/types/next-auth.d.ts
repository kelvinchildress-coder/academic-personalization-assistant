/**
 * Type augmentation for Auth.js v5. Currently we only extend the session
 * shape implicitly (email + name are already on session.user by default),
 * but this file is the right place to add custom fields like `role` once
 * the head-coach allow-list lands in Phase 7 Part 5.
 */
import "next-auth";

declare module "next-auth" {
  // Reserved for future custom fields (e.g., role: "coach" | "head_coach").
  // Intentionally empty in Part 2.
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  interface Session {}
}

declare module "next-auth/jwt" {
  // Same — empty for now, ready for Part 5 to add `role`.
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  interface JWT {}
}
