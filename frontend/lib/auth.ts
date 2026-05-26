import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import type { Session } from "next-auth";
import { authConfig } from "./auth.config";

export const { handlers, signIn, signOut, auth } = NextAuth({
  ...authConfig,
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async signIn({ user }) {
      // Open registration — any verified Google account is allowed
      return !!user.email;
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
