"use client";
import { createContext, useContext, useEffect, useState } from "react";

type ResolvedTheme = "light" | "dark";

const ThemeContext = createContext<{
  resolvedTheme: ResolvedTheme;
  setTheme: (t: "light" | "dark" | "system") => void;
}>({ resolvedTheme: "light", setTheme: () => {} });

function getResolved(stored: string | null): ResolvedTheme {
  if (stored === "dark") return "dark";
  if (stored === "light") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [resolvedTheme, setResolved] = useState<ResolvedTheme>("light");

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const resolved = getResolved(stored);
    setResolved(resolved);
    document.documentElement.classList.toggle("dark", resolved === "dark");
  }, []);

  const setTheme = (t: "light" | "dark" | "system") => {
    localStorage.setItem("theme", t);
    const resolved = getResolved(t === "system" ? null : t);
    document.documentElement.classList.toggle("dark", resolved === "dark");
    setResolved(resolved);
  };

  return (
    <ThemeContext.Provider value={{ resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
