import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "./auth.config";
import { readAgeGate } from "./age-gate";

const IS_DEV = process.env.NODE_ENV !== "production";

export const { handlers, signIn, signOut, auth } = NextAuth({
  ...authConfig,
  providers: [
    ...(IS_DEV
      ? [
          Credentials({
            id: "dev-credentials",
            name: "Dev Login",
            credentials: { email: { label: "Email", type: "email" } },
            authorize: async (creds) => {
              const email = creds?.email as string | undefined;
              if (!email) return null;
              return { id: email, email, name: email };
            },
          }),
        ]
      : []),
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async signIn({ user }) {
      // Sign-in doubles as signup, so nobody gets an account without passing
      // the age gate (/api/age-check), whichever provider they use.
      if ((await readAgeGate()) !== "eligible") return false;
      return !!user.email;
    },

    async jwt({ token, profile }) {
      if (profile) {
        token.picture = (profile as { picture?: string }).picture;
      }
      // Never keep provider tokens in the session: anything here is readable by
      // client JS via /api/auth/session. Backend tokens come from /api/auth/backend-token.
      // Also scrubs the field from sessions issued before this was removed.
      delete token.idToken;
      return token;
    },
  },
});
