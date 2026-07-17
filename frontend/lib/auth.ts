import { createHmac } from "crypto";
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";
import type { Session } from "next-auth";
import { authConfig } from "./auth.config";

const IS_DEV = process.env.NODE_ENV !== "production";

// Mint a backend-compatible HS256 JWT (matches what python-jose expects).
function mintDevToken(email: string, name: string): string {
  const secret = process.env.NEXTAUTH_SECRET ?? "";
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const body = Buffer.from(
    JSON.stringify({ email, name, iat: now, exp: now + 86400 })
  ).toString("base64url");
  const sig = createHmac("sha256", secret).update(`${header}.${body}`).digest("base64url");
  return `${header}.${body}.${sig}`;
}

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
      return !!user.email;
    },

    async jwt({ token, account, profile, user }) {
      if (account?.id_token) {
        token.idToken = account.id_token;
      }
      if (profile) {
        token.picture = (profile as { picture?: string }).picture;
      }
      // Dev credentials: mint a signed token the backend will accept
      if (account?.provider === "dev-credentials" && user?.email) {
        token.email = user.email;
        token.name = user.name ?? user.email;
        token.idToken = mintDevToken(user.email, user.name ?? user.email);
      }
      return token;
    },

    async session({ session, token }) {
      (session as Session & { apiToken?: string }).apiToken = token.idToken as string | undefined;
      return session;
    },
  },
});
