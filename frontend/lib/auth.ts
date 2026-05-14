import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import type { Session } from "next-auth";

// Server-side calls go via the internal Docker network URL, not localhost
const INTERNAL_API = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt" },
  callbacks: {
    async signIn({ user }) {
      const email = user.email;
      if (!email) return false;

      try {
        const res = await fetch(
          `${INTERNAL_API}/auth/check-access?email=${encodeURIComponent(email)}`,
          { headers: { "X-Internal-Secret": process.env.NEXTAUTH_SECRET! } }
        );
        return res.ok;
      } catch {
        // Backend unreachable — deny sign-in to fail secure
        return false;
      }
    },

    async jwt({ token, account, profile }) {
      if (account?.id_token) {
        token.idToken = account.id_token;
      }
      if (profile) {
        token.picture = (profile as { picture?: string }).picture;
      }
      return token;
    },

    async session({ session, token }) {
      (session as Session & { apiToken?: string }).apiToken = token.idToken as string | undefined;
      return session;
    },
  },
});
