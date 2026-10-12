import { createHmac, timingSafeEqual } from "crypto";
import { cookies } from "next/headers";

// Server-only. Signup happens on first sign-in (the backend creates the account
// from the first authenticated request), so the gate is enforced in the Auth.js
// signIn callback, not just in the login UI.
//
// The threshold is deliberately never sent to the browser: a neutral age screen
// asks for a date of birth without hinting at the cutoff.
export const MIN_SIGNUP_AGE = 18;

const COOKIE_NAME = "voxly_age_gate";
const ELIGIBLE_MAX_AGE = 60 * 60 * 24 * 365;
// Long enough that re-entering a different birth date right away doesn't work.
const BLOCKED_MAX_AGE = 60 * 60 * 24 * 30;

export type AgeGateStatus = "eligible" | "blocked";

function signature(payload: string): Buffer {
  return createHmac("sha256", process.env.NEXTAUTH_SECRET ?? "")
    .update(`voxly-age-gate:v1:${payload}`)
    .digest();
}

function encode(status: AgeGateStatus): string {
  const payload = `${status}.${Date.now()}`;
  return `${payload}.${signature(payload).toString("base64url")}`;
}

function decode(value: string | undefined): AgeGateStatus | null {
  if (!value) return null;
  const i = value.lastIndexOf(".");
  if (i < 0) return null;
  const payload = value.slice(0, i);
  const given = Buffer.from(value.slice(i + 1), "base64url");
  const expected = signature(payload);
  if (given.length !== expected.length || !timingSafeEqual(given, expected)) return null;
  const status = payload.split(".")[0];
  return status === "eligible" || status === "blocked" ? status : null;
}

export async function readAgeGate(): Promise<AgeGateStatus | null> {
  return decode((await cookies()).get(COOKIE_NAME)?.value);
}

export async function writeAgeGate(status: AgeGateStatus): Promise<void> {
  (await cookies()).set(COOKIE_NAME, encode(status), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: status === "eligible" ? ELIGIBLE_MAX_AGE : BLOCKED_MAX_AGE,
  });
}

/** Age in whole years for a YYYY-MM-DD date of birth, or null if it isn't a real, plausible date. */
export function ageFromDateOfBirth(dob: string, today = new Date()): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dob);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(Date.UTC(y, mo - 1, d));
  // Rejects impossible dates like 2001-02-30, which Date.UTC silently rolls over.
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== mo - 1 || date.getUTCDate() !== d) return null;

  let age = today.getUTCFullYear() - y;
  const beforeBirthday =
    today.getUTCMonth() < mo - 1 || (today.getUTCMonth() === mo - 1 && today.getUTCDate() < d);
  if (beforeBirthday) age--;
  return age >= 0 && age <= 120 ? age : null;
}
