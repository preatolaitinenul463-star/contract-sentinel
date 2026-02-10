"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Shield, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/api";

function getPasswordStrength(password: string): { level: number; label: string } {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 1) return { level: 1, label: "弱 - 建议增加大小写字母和数字" };
  if (score <= 2) return { level: 2, label: "一般 - 建议增加特殊字符" };
  if (score <= 3) return { level: 3, label: "较强" };
  return { level: 4, label: "非常强" };
}

function getPasswordByteLength(password: string): number {
  return new TextEncoder().encode(password).length;
}

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    if (password.length < 8) {
      setError("密码长度至少为8位");
      return;
    }
    if (getPasswordByteLength(password) > 72) {
      setError("密码过长，最多72字节（建议 8-32 位）");
      return;
    }

    setIsLoading(true);

    try {
      await authApi.register({ email, password, full_name: fullName || undefined });
      router.push("/auth/login?registered=true");
    } catch (err: any) {
      setError(err.message || "注册失败");
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
          <h1 className="mt-4 text-2xl font-bold">注册合同哨兵</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            创建账号开始使用
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
            <label className="text-sm font-medium">姓名（选填）</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="您的姓名"
              className="mt-1 w-full rounded-lg border bg-background px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

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
                placeholder="至少8位"
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
            {/* Password strength indicator */}
            {password && (
              <div className="mt-2">
                <div className="flex gap-1">
                  {[1, 2, 3, 4].map((level) => {
                    const strength = getPasswordStrength(password);
                    return (
                      <div
                        key={level}
                        className={`h-1.5 flex-1 rounded-full transition-colors ${
                          level <= strength.level
                            ? strength.level <= 1
                              ? "bg-red-500"
                              : strength.level <= 2
                              ? "bg-yellow-500"
                              : strength.level <= 3
                              ? "bg-blue-500"
                              : "bg-green-500"
                            : "bg-muted"
                        }`}
                      />
                    );
                  })}
                </div>
                <p className={`mt-1 text-xs ${
                  getPasswordStrength(password).level <= 1 ? "text-red-500" :
                  getPasswordStrength(password).level <= 2 ? "text-yellow-500" :
                  getPasswordStrength(password).level <= 3 ? "text-blue-500" : "text-green-500"
                }`}>
                  {getPasswordStrength(password).label}
                </p>
              </div>
            )}
          </div>

          <div>
            <label className="text-sm font-medium">确认密码</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="再次输入密码"
              required
              maxLength={72}
              className="mt-1 w-full rounded-lg border bg-background px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" required className="mt-1 h-4 w-4" />
            <span className="text-muted-foreground">
              我已阅读并同意{" "}
              <Link href="/terms" className="text-primary hover:underline" target="_blank">《用户协议》</Link>
              {" "}和{" "}
              <Link href="/privacy" className="text-primary hover:underline" target="_blank">《隐私政策》</Link>
            </span>
          </label>

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "注册中..." : "注册"}
          </Button>
        </form>

        {/* Links */}
        <div className="text-center text-sm">
          <span className="text-muted-foreground">已有账号？</span>{" "}
          <Link href="/auth/login" className="text-primary hover:underline">
            立即登录
          </Link>
        </div>
      </div>
    </div>
  );
}
