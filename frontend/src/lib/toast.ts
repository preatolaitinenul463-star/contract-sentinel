/**
 * Simple imperative toast notification system.
 * Works anywhere without React context.
 */

type ToastVariant = "default" | "destructive" | "success";

interface ToastOptions {
  title?: string;
  description: string;
  variant?: ToastVariant;
  duration?: number;
}

let _container: HTMLElement | null = null;

function getContainer(): HTMLElement {
  if (_container && document.body.contains(_container)) return _container;

  _container = document.createElement("div");
  _container.id = "toast-container";
  _container.style.cssText =
    "position:fixed;bottom:16px;right:16px;z-index:9999;display:flex;flex-direction:column-reverse;gap:8px;max-width:400px;width:100%;pointer-events:none;";
  document.body.appendChild(_container);
  return _container;
}

function createToastElement(options: ToastOptions): HTMLElement {
  const el = document.createElement("div");
  el.style.cssText =
    "pointer-events:auto;padding:12px 16px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:all 0.3s ease;transform:translateX(100%);opacity:0;font-size:14px;line-height:1.5;";

  if (options.variant === "destructive") {
    el.style.backgroundColor = "#ef4444";
    el.style.color = "white";
    el.style.border = "1px solid #dc2626";
  } else if (options.variant === "success") {
    el.style.backgroundColor = "#22c55e";
    el.style.color = "white";
    el.style.border = "1px solid #16a34a";
  } else {
    el.style.backgroundColor = "var(--background, white)";
    el.style.color = "var(--foreground, black)";
    el.style.border = "1px solid var(--border, #e5e7eb)";
  }

  let html = "";
  if (options.title) {
    html += `<div style="font-weight:600;margin-bottom:2px;">${options.title}</div>`;
  }
  html += `<div style="opacity:0.9;">${options.description}</div>`;
  el.innerHTML = html;

  return el;
}

export function showToast(options: ToastOptions) {
  if (typeof window === "undefined") return;

  const container = getContainer();
  const el = createToastElement(options);
  container.appendChild(el);

  // Animate in
  requestAnimationFrame(() => {
    el.style.transform = "translateX(0)";
    el.style.opacity = "1";
  });

  // Auto dismiss
  const duration = options.duration ?? 4000;
  setTimeout(() => {
    el.style.transform = "translateX(100%)";
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 300);
  }, duration);
}

export function toastSuccess(description: string, title?: string) {
  showToast({ description, title, variant: "success" });
}

export function toastError(description: string, title?: string) {
  showToast({ description, title: title || "错误", variant: "destructive" });
}

export function toastInfo(description: string, title?: string) {
  showToast({ description, title, variant: "default" });
}
