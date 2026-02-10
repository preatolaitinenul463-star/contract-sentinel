import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { AuthGuard } from "@/components/auth-guard";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "合同哨兵 - 智能合同审核平台",
  description: "基于多Agent AI流水线的智能合同审核、对比与法律助手平台。支持合同风险识别、条款级Redline对比和实时法律问答。",
  keywords: "合同审核,AI法务,合同对比,法律风险,智能审核,合同哨兵",
  openGraph: {
    title: "合同哨兵 - 智能合同审核平台",
    description: "AI 驱动的合同审核、对比与法律助手",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-background antialiased">
        <AppShell>
          <AuthGuard>{children}</AuthGuard>
        </AppShell>
        <Toaster />
      </body>
    </html>
  );
}
