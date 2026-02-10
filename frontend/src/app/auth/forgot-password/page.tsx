"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, ArrowLeft, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        setSent(true);
      } else {
        const data = await response.json();
        setError(data.detail || "请求失败");
      }
    } catch {
      setError("网络错误，请稍后重试");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8 rounded-lg border bg-card p-8">
        <div className="flex flex-col items-center">
          <Shield className="h-12 w-12 text-primary" />
          <h1 className="mt-4 text-2xl font-bold">忘记密码</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            输入注册邮箱，我们将发送重置链接
          </p>
        </div>

        {sent ? (
          <div className="text-center space-y-4">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <Mail className="h-8 w-8 text-green-600" />
            </div>
            <p className="text-sm text-muted-foreground">
              如果该邮箱已注册，重置链接已发送到 <strong>{email}</strong>。
              请查收邮件并在30分钟内完成重置。
            </p>
            <Link href="/auth/login" className="text-sm text-primary hover:underline">
              返回登录
            </Link>
          </div>
        ) : (
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

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "发送中..." : "发送重置链接"}
            </Button>
          </form>
        )}

        <div className="text-center">
          <Link
            href="/auth/login"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            返回登录
          </Link>
        </div>
      </div>
    </div>
  );
}
