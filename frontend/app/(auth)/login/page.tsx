"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const ERROR_MESSAGES: Record<string, { title: string; body: string }> = {
  AccessDenied: {
    title: "Access denied",
    body: "Your Google account is not on the authorized list. Contact the admin to request access.",
  },
  Configuration: {
    title: "Server configuration error",
    body: "There is a problem with the server setup. Please try again or contact support.",
  },
  Verification: {
    title: "Sign-in link expired",
    body: "The sign-in link has expired or already been used. Please request a new one.",
  },
  Default: {
    title: "Something went wrong",
    body: "An unexpected error occurred during sign-in. Please try again.",
  },
};

function LoginCard() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const errorInfo = error ? (ERROR_MESSAGES[error] ?? ERROR_MESSAGES.Default) : null;

  return (
    <Card className="w-full max-w-md mx-4">
      <CardHeader className="text-center">
        <div className="w-12 h-12 bg-primary rounded-xl mx-auto mb-4 flex items-center justify-center">
          <img src="/logo.svg" alt="VoxlyAI" className="w-8 h-8" />
        </div>
        <CardTitle className="text-2xl">VoxlyAI</CardTitle>
        <CardDescription>
          Your voice, amplified. Create content that sounds like you — across every platform.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {errorInfo && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 text-center">
            <p className="font-medium">{errorInfo.title}</p>
            <p className="mt-0.5 text-red-600">{errorInfo.body}</p>
          </div>
        )}
        <Button
          className="w-full gap-3"
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          {errorInfo ? "Try again with Google" : "Continue with Google"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Access is restricted to authorized accounts only.
        </p>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginCard />
    </Suspense>
  );
}
