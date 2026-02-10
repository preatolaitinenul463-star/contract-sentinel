"use client";

import { useState, useEffect } from "react";
import { FileText, GitCompare, Clock, Loader2, AlertTriangle } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface HistoryItem {
  id: number;
  type: "review" | "compare";
  filename: string;
  status: string;
  contract_type: string;
  created_at: string;
}

const contractTypeLabels: Record<string, string> = {
  general: "通用合同",
  labor: "劳动合同",
  tech: "技术合同",
  sales: "买卖合同",
  lease: "租赁合同",
  nda: "保密协议",
  service: "服务合同",
  other: "其他",
};

export default function HistoryPage() {
  const { token } = useAuthStore();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"all" | "review" | "compare">("all");

  useEffect(() => {
    loadHistory();
  }, [token]);

  const loadHistory = async () => {
    if (!token) return;
    setLoading(true);

    try {
      // Load contracts (which represent reviews)
      const contractsResp = await fetch("/api/contracts?page=1&page_size=50", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const contractsData = contractsResp.ok ? await contractsResp.json() : { items: [] };

      const contractItems: HistoryItem[] = (contractsData.items || []).map((c: any) => ({
        id: c.id,
        type: "review" as const,
        filename: c.filename,
        status: c.status,
        contract_type: c.contract_type,
        created_at: c.created_at,
      }));

      setItems(contractItems);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const filtered = tab === "all" ? items : items.filter((i) => i.type === tab);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">历史记录</h1>
        <p className="text-muted-foreground">查看您的所有合同审核和对比记录</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {[
          { key: "all", label: "全部" },
          { key: "review", label: "审核" },
          { key: "compare", label: "对比" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as any)}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              tab === t.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-accent"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>暂无历史记录</p>
          <p className="text-sm mt-1">上传合同开始审核吧</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <div
              key={`${item.type}-${item.id}`}
              className="flex items-center gap-4 rounded-lg border bg-card p-4 hover:bg-accent/50 transition-colors"
            >
              {item.type === "review" ? (
                <FileText className="h-5 w-5 text-blue-500 shrink-0" />
              ) : (
                <GitCompare className="h-5 w-5 text-purple-500 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{item.filename}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {contractTypeLabels[item.contract_type] || item.contract_type}
                  {" "}·{" "}
                  {item.type === "review" ? "合同审核" : "合同对比"}
                </p>
              </div>
              <div className="text-right shrink-0">
                <span
                  className={cn(
                    "inline-block rounded px-2 py-0.5 text-xs",
                    item.status === "reviewed"
                      ? "bg-green-100 text-green-700"
                      : item.status === "error"
                      ? "bg-red-100 text-red-700"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {item.status === "reviewed" ? "已审核" : item.status === "uploaded" ? "已上传" : item.status}
                </span>
                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1 justify-end">
                  <Clock className="h-3 w-3" />
                  {new Date(item.created_at).toLocaleDateString("zh-CN")}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
