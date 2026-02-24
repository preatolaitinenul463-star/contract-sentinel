"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  FileText,
  GitCompare,
  MessageSquare,
  Settings,
  Shield,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "首页", href: "/", icon: Home },
  { name: "合同审核", href: "/review", icon: FileText },
  { name: "合同对比", href: "/compare", icon: GitCompare },
  { name: "法律助手", href: "/assistant", icon: MessageSquare },
  { name: "审核标准", href: "/policy", icon: Shield },
  { name: "设置", href: "/settings", icon: Settings },
];

interface SidebarProps {
  open?: boolean;
  onClose?: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <div
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex h-full w-64 flex-col border-r bg-card transition-transform duration-200 md:static md:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b px-6">
        <div className="flex items-center gap-2">
          <Shield className="h-8 w-8 text-primary" />
          <span className="text-xl font-bold">合同哨兵</span>
        </div>
        {/* Close button (mobile only) */}
        <button
          className="rounded-lg p-1 text-muted-foreground hover:bg-accent md:hidden"
          onClick={onClose}
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-4">
        <div className="rounded-lg bg-muted p-3">
          <p className="text-xs font-medium">当前版本：全免费</p>
          <p className="mt-1 text-xs text-muted-foreground">
            无付费墙，无套餐限制
          </p>
        </div>
        <div className="mt-3 text-[11px] text-muted-foreground space-y-1">
          <p>审核结果仅供参考，不构成法律意见。</p>
          <div className="flex gap-2">
            <Link href="/terms" className="hover:underline">用户协议</Link>
            <Link href="/privacy" className="hover:underline">隐私政策</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
