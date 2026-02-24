"use client";

import { useEffect, useState } from "react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  // Keep hydration guard only to avoid layout flicker.
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  if (!hydrated) {
    return <>{children}</>;
  }

  return <>{children}</>;
}
