"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useTheme } from "@/components/theme-provider";

declare global {
  interface Window {
    turnstile: {
      render: (el: HTMLElement | string, opts: Record<string, unknown>) => string;
      reset: (id: string) => void;
      remove: (id: string) => void;
    };
    __turnstileReady?: () => void;
  }
}

const ERROR_MESSAGES: Record<string, { title: string; body: string }> = {
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
  const { resolvedTheme } = useTheme();

  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const widgetIdRef = useRef<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const renderWidget = (theme: string) => {
    if (!containerRef.current || !window.turnstile) return;
    if (widgetIdRef.current) {
      window.turnstile.remove(widgetIdRef.current);
      widgetIdRef.current = null;
    }
    setCaptchaToken(null);
    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "",
      theme: theme === "dark" ? "dark" : "light",
      callback: (token: unknown) => setCaptchaToken(token as string),
      "expired-callback": () => setCaptchaToken(null),
      "error-callback": () => setCaptchaToken(null),
    });
  };

  // Load Turnstile script once
  useEffect(() => {
    if (window.turnstile) {
      renderWidget(resolvedTheme ?? "light");
      return;
    }
    window.__turnstileReady = () => renderWidget(resolvedTheme ?? "light");
    const script = document.createElement("script");
    script.src =
      "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=__turnstileReady";
    script.async = true;
    document.head.appendChild(script);
  }, []);

  // Re-render widget when theme switches
  useEffect(() => {
    if (window.turnstile) renderWidget(resolvedTheme ?? "light");
  }, [resolvedTheme]);

  const handleSignIn = async () => {
    if (!captchaToken || verifying) return;
    setVerifying(true);
    try {
      const res = await fetch("/api/verify-captcha", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: captchaToken }),
      });
      if (!res.ok) {
        if (widgetIdRef.current) window.turnstile.reset(widgetIdRef.current);
        setCaptchaToken(null);
        setVerifying(false);
        return;
      }
      signIn("google", { callbackUrl: "/dashboard" });
    } catch {
      setCaptchaToken(null);
      setVerifying(false);
    }
  };

  return (
    <Card className="w-full max-w-md mx-4">
      <CardHeader className="text-center">
        <div className="w-12 h-12 bg-primary rounded-xl mx-auto mb-4 flex items-center justify-center">
          <img src="/logo.svg" alt="VoxlyAI" className="w-8 h-8" />
        </div>
        <CardTitle className="text-2xl">VoxlyAI</CardTitle>
        <CardDescription>
          Your voice, amplified. Create content that sounds like you, across every platform.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {errorInfo && (
          <div className="rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-center">
            <p className="font-medium text-red-700 dark:text-red-400">{errorInfo.title}</p>
            <p className="mt-0.5 text-red-600 dark:text-red-500">{errorInfo.body}</p>
          </div>
        )}

        {/* Cloudflare Turnstile */}
        <div className="flex justify-center">
          <div ref={containerRef} />
        </div>

        <Button
          className="w-full gap-3"
          onClick={handleSignIn}
          disabled={!captchaToken || verifying}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          {verifying ? "Verifying…" : errorInfo ? "Try again with Google" : "Continue with Google"}
        </Button>

        <p className="text-center text-xs text-muted-foreground">
          Free to use · Your data stays private
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
