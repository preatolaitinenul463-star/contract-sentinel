"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Shield, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";
import { authApi } from "@/lib/api";

function getPasswordByteLength(password: string): number {
  return new TextEncoder().encode(password).length;
}

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (getPasswordByteLength(password) > 72) {
      setError("密码过长，最多72字节（建议 8-32 位）");
      return;
    }
    setIsLoading(true);

    try {
      const tokenData = await authApi.login({ email, password });
      const userData = await authApi.me(tokenData.access_token);
      login(userData as any, tokenData.access_token);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "登录失败");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8 rounded-lg border bg-card p-8">
        {/* Logo */}
        <div className="flex flex-col items-center">
          <Shield className="h-12 w-12 text-primary" />
          <h1 className="mt-4 text-2xl font-bold">登录合同哨兵</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            智能合同审核平台
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <div>
            <label className="text-sm font-medium">邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              required
              className="mt-1 w-full rounded-lg border bg-background px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="text-sm font-medium">密码</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                maxLength={72}
                className="mt-1 w-full rounded-lg border bg-background px-4 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "登录中..." : "登录"}
          </Button>
        </form>

        {/* Links */}
        <div className="space-y-2 text-center text-sm">
          <div>
            <Link href="/auth/forgot-password" className="text-muted-foreground hover:text-primary">
              忘记密码？
            </Link>
          </div>
          <div>
            <span className="text-muted-foreground">还没有账号？</span>{" "}
            <Link href="/auth/register" className="text-primary hover:underline">
              立即注册
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
