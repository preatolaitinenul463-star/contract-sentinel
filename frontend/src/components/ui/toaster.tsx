"use client";

import * as React from "react";
import * as Toast from "@radix-ui/react-toast";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

interface ToastProps {
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
}

interface ToastContextType {
  toast: (props: ToastProps) => void;
}

const ToastContext = React.createContext<ToastContextType | null>(null);

export function useToast() {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

export function Toaster() {
  const [toasts, setToasts] = React.useState<(ToastProps & { id: string })[]>(
    []
  );

  const toast = React.useCallback((props: ToastProps) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { ...props, id }]);
  }, []);

  const removeToast = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      <Toast.Provider swipeDirection="right">
        {toasts.map((t) => (
          <Toast.Root
            key={t.id}
            className={cn(
              "group pointer-events-auto relative flex w-full items-center justify-between space-x-2 overflow-hidden rounded-md border p-4 pr-6 shadow-lg transition-all",
              t.variant === "destructive"
                ? "border-destructive bg-destructive text-destructive-foreground"
                : "border bg-background"
            )}
            onOpenChange={(open) => {
              if (!open) removeToast(t.id);
            }}
          >
            <div className="grid gap-1">
              {t.title && (
                <Toast.Title className="text-sm font-semibold">
                  {t.title}
                </Toast.Title>
              )}
              {t.description && (
                <Toast.Description className="text-sm opacity-90">
                  {t.description}
                </Toast.Description>
              )}
            </div>
            <Toast.Close className="absolute right-1 top-1 rounded-md p-1 opacity-0 transition-opacity hover:bg-secondary group-hover:opacity-100">
              <X className="h-4 w-4" />
            </Toast.Close>
          </Toast.Root>
        ))}
        <Toast.Viewport className="fixed bottom-0 right-0 z-[100] flex max-h-screen w-full flex-col-reverse gap-2 p-4 sm:max-w-[420px]" />
      </Toast.Provider>
    </ToastContext.Provider>
  );
}
