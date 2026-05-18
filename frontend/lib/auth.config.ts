import type { NextAuthConfig } from "next-auth";

export const authConfig: NextAuthConfig = {
  secret: process.env.NEXTAUTH_SECRET,
  trustHost: true,
  session: { strategy: "jwt" },
  pages: { signIn: "/login", error: "/login" },
  providers: [],
  callbacks: {
    authorized({ auth }) {
      return !!auth?.user;
    },
  },
};
