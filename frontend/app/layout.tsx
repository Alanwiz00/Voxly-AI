import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { SessionProvider } from "next-auth/react";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXTAUTH_URL ?? "https://app.voxlyai.online"),
  title: {
    default: "VoxlyAI — Your Voice, Amplified",
    template: "%s — VoxlyAI",
  },
  description:
    "AI that learns your writing style and generates platform-native posts that sound like you — across Twitter, Instagram, Facebook, and Telegram.",
  keywords: [
    "AI content generator",
    "social media content AI",
    "AI writing assistant",
    "Twitter content generator",
    "Instagram captions AI",
    "content creation tool",
    "VoxlyAI",
  ],
  authors: [{ name: "VoxlyAI", url: "https://app.voxlyai.online" }],
  creator: "VoxlyAI",
  robots: { index: false, follow: false },
  openGraph: {
    type: "website",
    siteName: "VoxlyAI",
    title: "VoxlyAI — Your Voice, Amplified",
    description:
      "AI that learns your writing style and generates platform-native posts that sound like you — across Twitter, Instagram, Facebook, and Telegram.",
    url: "https://app.voxlyai.online",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "VoxlyAI — Your Voice, Amplified" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "VoxlyAI — Your Voice, Amplified",
    description:
      "AI that learns your writing style and generates posts that sound like you — not like a robot.",
    images: ["/og-image.png"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
        <ThemeProvider>
          <SessionProvider>
            {children}
            <Toaster richColors position="top-right" />
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
