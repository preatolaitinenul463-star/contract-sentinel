"use client";

import { Bell, User, LogOut, Settings, Menu, ChevronRight, Home } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { ThemeToggle } from "@/components/theme-toggle";

const routeNames: Record<string, string> = {
  "/": "首页",
  "/review": "合同审核",
  "/compare": "合同对比",
  "/assistant": "法律助手",
  "/settings": "设置",
  "/pricing": "套餐价格",
  "/oversight": "审阅工作台",
  "/history": "历史记录",
  "/auth/login": "登录",
  "/auth/register": "注册",
  "/terms": "用户协议",
  "/privacy": "隐私政策",
};

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { user, isAuthenticated, logout } = useAuthStore();
  const pathname = usePathname();

  // Generate breadcrumb
  const pageName = routeNames[pathname] || "页面";

  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-4 md:px-6">
      {/* Left: hamburger + breadcrumb */}
      <div className="flex items-center gap-3">
        {/* Hamburger menu (mobile only) */}
        <button
          className="rounded-lg p-2 text-muted-foreground hover:bg-accent md:hidden"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Breadcrumb */}
        <nav className="hidden items-center gap-1 text-sm text-muted-foreground sm:flex">
          <Link href="/" className="hover:text-foreground">
            <Home className="h-4 w-4" />
          </Link>
          {pathname !== "/" && (
            <>
              <ChevronRight className="h-3 w-3" />
              <span className="font-medium text-foreground">{pageName}</span>
            </>
          )}
        </nav>
        {/* Mobile: just show page name */}
        <span className="text-sm font-medium sm:hidden">{pageName}</span>
      </div>

      {/* Right side actions */}
      <div className="flex items-center gap-1 md:gap-3">
        {/* Theme toggle */}
        <ThemeToggle />

        {/* Notifications */}
        <button className="rounded-lg p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground">
          <Bell className="h-5 w-5" />
        </button>

        {/* User Menu */}
        {isAuthenticated ? (
          <div className="relative group">
            <button className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-accent md:px-3 md:py-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <User className="h-4 w-4" />
              </div>
              <span className="hidden text-sm font-medium md:inline">
                {user?.full_name || user?.email}
              </span>
            </button>

            {/* Dropdown */}
            <div className="absolute right-0 top-full mt-1 hidden w-48 rounded-lg border bg-card py-1 shadow-lg group-hover:block z-50">
              <Link
                href="/settings"
                className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-accent"
              >
                <Settings className="h-4 w-4" />
                设置
              </Link>
              <button
                onClick={logout}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-destructive hover:bg-accent"
              >
                <LogOut className="h-4 w-4" />
                退出登录
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Link
              href="/auth/login"
              className="rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-accent md:px-4 md:py-2"
            >
              登录
            </Link>
            <Link
              href="/auth/register"
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 md:px-4 md:py-2"
            >
              注册
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
