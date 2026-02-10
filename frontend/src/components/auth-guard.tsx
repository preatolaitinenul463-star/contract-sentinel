"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "@/lib/store";

// Routes that require authentication
const PROTECTED_ROUTES = ["/review", "/compare", "/assistant", "/settings", "/history", "/team"];

// Routes that are always public
const PUBLIC_ROUTES = ["/", "/auth", "/pricing", "/terms", "/privacy"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();
  // Wait for Zustand persist store to hydrate from localStorage
  // to prevent false "not authenticated" flash on first render
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  const isProtected = PROTECTED_ROUTES.some((route) => pathname.startsWith(route));

  useEffect(() => {
    if (hydrated && isProtected && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [hydrated, isProtected, isAuthenticated, router]);

  // Before hydration, render children normally (avoid flash)
  if (!hydrated) {
    return <>{children}</>;
  }

  // After hydration, if on a protected route and not authenticated, show loading
  if (isProtected && !isAuthenticated) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
          <p className="text-sm text-muted-foreground">请先登录...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
