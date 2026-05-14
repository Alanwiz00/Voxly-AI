import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isLoggedIn = !!req.auth;

  const publicPaths = ["/login"];
  if (publicPaths.includes(pathname)) {
    if (isLoggedIn) return NextResponse.redirect(new URL("/dashboard", req.url));
    return NextResponse.next();
  }

  if (!isLoggedIn) return NextResponse.redirect(new URL("/login", req.url));
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
