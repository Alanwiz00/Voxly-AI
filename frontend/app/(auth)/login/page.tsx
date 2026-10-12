import { Suspense } from "react";
import { readAgeGate } from "@/lib/age-gate";
import { LoginCard } from "./login-card";

export default async function LoginPage() {
  // The age-gate cookie is httpOnly, so its status is read here and passed down.
  const ageGate = await readAgeGate();
  return (
    <Suspense fallback={null}>
      <LoginCard ageGate={ageGate} />
    </Suspense>
  );
}
