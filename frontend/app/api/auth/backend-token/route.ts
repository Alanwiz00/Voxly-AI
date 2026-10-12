import { auth } from "@/lib/auth";
import { SignJWT } from "jose";
import { NextResponse } from "next/server";

// The browser holds this bearer token in JS memory, so keep its lifetime short:
// a leaked token stops working quickly. lib/api.ts re-fetches before expiry.
const TOKEN_TTL_SECONDS = 60 * 60;

// Bearer tokens must never be stored by the browser or any proxy cache.
const NO_STORE = { "Cache-Control": "private, no-store" };

export async function GET() {
  const session = await auth();

  if (!session?.user?.email) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401, headers: NO_STORE });
  }

  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!);
  const token = await new SignJWT({
    email: session.user.email,
    name: session.user.name ?? "",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${TOKEN_TTL_SECONDS}s`)
    .sign(secret);

  return NextResponse.json({ token, expires_in: TOKEN_TTL_SECONDS }, { headers: NO_STORE });
}
