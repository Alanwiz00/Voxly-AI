import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const PLATFORM_LABELS: Record<string, string> = {
  twitter: "Twitter / X",
  instagram: "Instagram",
  facebook: "Facebook",
  telegram: "Telegram",
};

export const CONTENT_TYPE_LABELS: Record<string, string> = {
  idea: "Post Ideas",
  long_form: "Long-form Post",
  thread: "Thread",
  article: "Article",
};

export const PLATFORM_COLORS: Record<string, string> = {
  twitter: "bg-sky-100 text-sky-800",
  instagram: "bg-pink-100 text-pink-800",
  facebook: "bg-blue-100 text-blue-800",
  telegram: "bg-cyan-100 text-cyan-800",
};
