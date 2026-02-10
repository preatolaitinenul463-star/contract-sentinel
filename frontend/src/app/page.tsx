"use client";

import { useState, useEffect } from "react";
import { FileText, GitCompare, MessageSquare, Upload, ArrowRight, Clock, Shield } from "lucide-react";
import Link from "next/link";
import { useAuthStore } from "@/lib/store";

const features = [
  {
    title: "合同审核",
    description: "上传合同文件，AI自动识别风险条款，生成详细审核报告",
    icon: FileText,
    href: "/review",
    color: "bg-blue-500",
  },
  {
    title: "合同对比",
    description: "对比两份合同的差异，智能分析变更带来的风险影响",
    icon: GitCompare,
    href: "/compare",
    color: "bg-purple-500",
  },
  {
    title: "法律助手",
    description: "智能问答助手，基于法规库提供专业建议和条款参考",
    icon: MessageSquare,
    href: "/assistant",
    color: "bg-green-500",
  },
];

interface RecentContract {
  id: number;
  filename: string;
  status: string;
  created_at: string;
  contract_type: string;
}

export default function HomePage() {
  const { token, isAuthenticated, user } = useAuthStore();
  const [recentContracts, setRecentContracts] = useState<RecentContract[]>([]);
  const [usageStats, setUsageStats] = useState<any>(null);

  useEffect(() => {
    if (isAuthenticated && token) {
      // Load recent contracts
      fetch("/api/contracts?page=1&page_size=5", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.ok ? r.json() : null)
        .then((data) => {
          if (data?.items) setRecentContracts(data.items);
        })
        .catch(() => {});

      // Load usage stats
      fetch("/api/quota/usage", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.ok ? r.json() : null)
        .then((data) => {
          if (data) setUsageStats(data);
        })
        .catch(() => {});
    }
  }, [isAuthenticated, token]);

  const contractTypeLabels: Record<string, string> = {
    general: "通用合同",
    labor: "劳动合同",
    tech: "技术合同",
    sales: "买卖合同",
    lease: "租赁合同",
    nda: "保密协议",
    service: "服务合同",
  };

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div className="rounded-lg border bg-card p-6 md:p-8">
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
          {isAuthenticated ? `欢迎回来，${user?.full_name || "用户"}` : "欢迎使用合同哨兵"}
        </h1>
        <p className="mt-2 text-muted-foreground">
          智能合同审核、对比与法律助手平台，为您的合同安全保驾护航
        </p>
        {usageStats && (
          <div className="mt-4 flex flex-wrap gap-4">
            <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-1.5 text-sm">
              <Shield className="h-4 w-4 text-primary" />
              <span>本月审核: {usageStats.reviews_this_month} 次</span>
            </div>
            <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-1.5 text-sm">
              <GitCompare className="h-4 w-4 text-purple-500" />
              <span>本月对比: {usageStats.comparisons_this_month} 次</span>
            </div>
            <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-1.5 text-sm">
              <MessageSquare className="h-4 w-4 text-green-500" />
              <span>今日消息: {usageStats.assistant_messages_today} 条</span>
            </div>
          </div>
        )}
      </div>

      {/* Feature Cards */}
      <div className="grid gap-4 md:gap-6 sm:grid-cols-2 md:grid-cols-3">
        {features.map((feature) => (
          <Link
            key={feature.title}
            href={feature.href}
            className="group rounded-lg border bg-card p-5 md:p-6 transition-all hover:border-primary hover:shadow-md"
          >
            <div className={`inline-flex rounded-lg ${feature.color} p-3`}>
              <feature.icon className="h-6 w-6 text-white" />
            </div>
            <h2 className="mt-4 text-lg md:text-xl font-semibold">{feature.title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {feature.description}
            </p>
            <div className="mt-4 flex items-center text-sm font-medium text-primary">
              开始使用
              <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </div>
          </Link>
        ))}
      </div>

      {/* Quick Upload */}
      <div className="rounded-lg border bg-card p-6 md:p-8">
        <h2 className="text-xl font-semibold">快速开始</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          上传合同文件，立即开始智能审核
        </p>
        <div className="mt-6">
          <Link
            href="/review"
            className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Upload className="mr-2 h-4 w-4" />
            上传合同
          </Link>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold">最近活动</h2>
        {recentContracts.length > 0 ? (
          <div className="mt-4 space-y-3">
            {recentContracts.map((contract) => (
              <div
                key={contract.id}
                className="flex items-center gap-3 rounded-lg border p-3 text-sm"
              >
                <FileText className="h-5 w-5 text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{contract.filename}</p>
                  <p className="text-xs text-muted-foreground">
                    {contractTypeLabels[contract.contract_type] || contract.contract_type}
                    {" "}·{" "}
                    {new Date(contract.created_at).toLocaleDateString("zh-CN")}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {contract.status === "reviewed" ? "已审核" : contract.status === "uploaded" ? "已上传" : contract.status}
                </span>
              </div>
            ))}
            <Link
              href="/history"
              className="block text-center text-sm text-primary hover:underline pt-2"
            >
              查看全部历史记录
            </Link>
          </div>
        ) : (
          <div className="mt-4 flex items-center justify-center py-8 text-muted-foreground">
            <p>{isAuthenticated ? "暂无活动记录，上传合同开始使用" : "登录后查看活动记录"}</p>
          </div>
        )}
      </div>
    </div>
  );
}
