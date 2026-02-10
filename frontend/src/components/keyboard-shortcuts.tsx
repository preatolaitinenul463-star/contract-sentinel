"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Global keyboard shortcuts handler.
 * - Ctrl+K / Cmd+K: Focus search / navigate to assistant
 * - Ctrl+Shift+N: New review
 */
export function KeyboardShortcuts() {
  const router = useRouter();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;

      // Ctrl+K: Go to assistant (search/ask)
      if (isCtrl && e.key === "k") {
        e.preventDefault();
        router.push("/assistant");
      }

      // Ctrl+Shift+N: New review
      if (isCtrl && e.shiftKey && e.key === "N") {
        e.preventDefault();
        router.push("/review");
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router]);

  return null;
}
