import { NextResponse } from "next/server";
import { MIN_SIGNUP_AGE, ageFromDateOfBirth, readAgeGate, writeAgeGate } from "@/lib/age-gate";

const NO_STORE = { "Cache-Control": "private, no-store" };

// Checks a date of birth and records only the outcome (eligible/blocked) in a
// signed cookie. The date itself is never stored or logged.
export async function POST(req: Request) {
  // A browser that already failed the check can't retry with a different date.
  if ((await readAgeGate()) === "blocked") {
    return NextResponse.json({ eligible: false }, { status: 403, headers: NO_STORE });
  }

  let dob: unknown;
  try {
    ({ dob } = await req.json());
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400, headers: NO_STORE });
  }

  const age = typeof dob === "string" ? ageFromDateOfBirth(dob) : null;
  if (age === null) {
    return NextResponse.json({ error: "Enter a valid date of birth." }, { status: 400, headers: NO_STORE });
  }

  const eligible = age >= MIN_SIGNUP_AGE;
  await writeAgeGate(eligible ? "eligible" : "blocked");
  return NextResponse.json({ eligible }, { status: eligible ? 200 : 403, headers: NO_STORE });
}
