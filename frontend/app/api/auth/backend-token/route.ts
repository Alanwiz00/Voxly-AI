import { auth } from "@/lib/auth";
import { SignJWT } from "jose";
import { NextResponse } from "next/server";

export async function GET() {
  const session = await auth();

  if (!session?.user?.email) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!);
  const token = await new SignJWT({
    email: session.user.email,
    name: session.user.name ?? "",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setExpirationTime("30d")
    .sign(secret);

  return NextResponse.json({ token });
}
