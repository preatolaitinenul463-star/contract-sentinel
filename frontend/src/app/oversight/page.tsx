"use client";

import { useState, useEffect } from "react";
import {
  Shield, CheckCircle, XCircle, Clock, AlertTriangle,
  ChevronDown, ChevronUp, ExternalLink, FileText,
  Loader2, Search, Filter, Eye, ThumbsUp, ThumbsDown,
  Globe, Lock, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const API_BASE =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000/api"
    : "/api";

interface PipelineRun {
  run_id: string;
  feature: string;
  mode: string | null;
  status: string;
  jurisdiction: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number;
  official_count: number;
  open_count: number;
  verification_passed: boolean;
  verification_count: number;
  result_summary: any;
  approval: {
    state: string;
    comment: string | null;
    export_enabled: boolean;
    updated_at: string | null;
  } | null;
  // detail fields (only when expanded)
  events?: any[];
  sources?: any[];
  verifications?: any[];
}

const featureLabels: Record<string, string> = {
  assistant: "法律助手",
  review: "合同审核",
  redline: "批阅/批注",
};

const statusConfig: Record<string, { color: string; icon: any; label: string }> = {
  running: { color: "text-blue-500", icon: Loader2, label: "进行中" },
  completed: { color: "text-green-600", icon: CheckCircle, label: "已完成" },
  failed: { color: "text-red-600", icon: XCircle, label: "失败" },
  degraded: { color: "text-amber-600", icon: AlertTriangle, label: "降级/待审" },
};

export default function OversightPage() {
  const { token, isAuthenticated } = useAuthStore();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const [detailCache, setDetailCache] = useState<Record<string, PipelineRun>>({});
  const [featureFilter, setFeatureFilter] = useState<string>("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadRuns = async () => {
    if (!token) return;
    setLoading(true);
    try {
      let url = `${API_BASE}/oversight/runs?page_size=50`;
      if (featureFilter) url += `&feature=${featureFilter}`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setRuns(await res.json());
    } catch (e) {
      console.error("Load runs failed:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated && token) loadRuns();
  }, [isAuthenticated, token, featureFilter]);

  const loadDetail = async (runId: string) => {
    if (detailCache[runId]) return;
    try {
      const res = await fetch(`${API_BASE}/oversight/runs/${runId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setDetailCache((prev) => ({ ...prev, [runId]: data }));
      }
    } catch (e) {
      console.error("Load detail failed:", e);
    }
  };

  const toggleExpand = async (runId: string) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
    } else {
      setExpandedRun(runId);
      await loadDetail(runId);
    }
  };

  const handleApproval = async (runId: string, action: "approve" | "reject") => {
    if (!token) return;
    setActionLoading(runId);
    try {
      const comment = action === "reject" ? prompt("请输入驳回理由：") : null;
      const res = await fetch(`${API_BASE}/oversight/runs/${runId}/${action}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ comment }),
      });
      if (res.ok) {
        await loadRuns();
        // refresh detail cache
        setDetailCache((prev) => {
          const updated = { ...prev };
          delete updated[runId];
          return updated;
        });
      }
    } catch (e) {
      console.error(`${action} failed:`, e);
    } finally {
      setActionLoading(null);
    }
  };

  const detail = expandedRun ? detailCache[expandedRun] : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6 text-primary" />
          审阅工作台
        </h1>
        <p className="text-muted-foreground">
          查看 AI 流水线运行记录、来源溯源、验证结果，审批后开放导出
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">筛选：</span>
        </div>
        {["", "assistant", "review", "redline"].map((f) => (
          <Button
            key={f}
            variant={featureFilter === f ? "default" : "outline"}
            size="sm"
            onClick={() => setFeatureFilter(f)}
          >
            {f ? featureLabels[f] || f : "全部"}
          </Button>
        ))}
        <Button variant="ghost" size="sm" onClick={loadRuns} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "刷新"}
        </Button>
      </div>

      {/* Runs list */}
      <div className="space-y-3">
        {runs.length === 0 && !loading && (
          <div className="text-center py-12 text-muted-foreground">
            暂无运行记录
          </div>
        )}

        {runs.map((run) => {
          const sc = statusConfig[run.status] || statusConfig.completed;
          const StatusIcon = sc.icon;
          const isExpanded = expandedRun === run.run_id;

          return (
            <div key={run.run_id} className="rounded-xl border bg-card shadow-sm">
              {/* Header row */}
              <button
                className="w-full flex items-center gap-4 p-4 text-left hover:bg-accent/50 transition-colors rounded-xl"
                onClick={() => toggleExpand(run.run_id)}
              >
                <StatusIcon
                  className={cn("h-5 w-5 shrink-0", sc.color,
                    run.status === "running" && "animate-spin")}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">
                      {featureLabels[run.feature] || run.feature}
                    </span>
                    {run.mode && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                        {run.mode}
                      </span>
                    )}
                    <span className={cn("text-xs font-medium", sc.color)}>
                      {sc.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{run.run_id}</span>
                    <span>{run.duration_ms}ms</span>
                    {run.started_at && (
                      <span>{new Date(run.started_at).toLocaleString("zh-CN")}</span>
                    )}
                  </div>
                </div>

                {/* Source badges */}
                <div className="flex items-center gap-2 shrink-0">
                  {run.official_count > 0 && (
                    <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400">
                      <Lock className="h-3 w-3" />{run.official_count} 官方
                    </span>
                  )}
                  {run.open_count > 0 && (
                    <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
                      <Globe className="h-3 w-3" />{run.open_count} 参考
                    </span>
                  )}
                  {!run.verification_passed && (
                    <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700 dark:bg-red-950/30">
                      <AlertTriangle className="h-3 w-3" />验证未通过
                    </span>
                  )}
                </div>

                {/* Approval badge */}
                {run.approval && (
                  <span className={cn(
                    "text-xs font-medium px-2 py-0.5 rounded-full",
                    run.approval.state === "approved" ? "bg-green-100 text-green-700" :
                    run.approval.state === "rejected" ? "bg-red-100 text-red-700" :
                    "bg-amber-100 text-amber-700"
                  )}>
                    {run.approval.state === "approved" ? "已通过" :
                     run.approval.state === "rejected" ? "已驳回" : "待审批"}
                  </span>
                )}

                {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </button>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="border-t px-4 pb-4 space-y-4">
                  {!detail ? (
                    <div className="flex items-center justify-center py-6">
                      <Loader2 className="h-5 w-5 animate-spin text-primary" />
                    </div>
                  ) : (
                    <>
                      {/* Actions */}
                      <div className="flex items-center gap-2 pt-3">
                        <Button
                          size="sm"
                          disabled={actionLoading === run.run_id || run.approval?.state === "approved"}
                          onClick={() => handleApproval(run.run_id, "approve")}
                        >
                          <ThumbsUp className="mr-1 h-3.5 w-3.5" />通过
                        </Button>
                        <Button
                          size="sm" variant="destructive"
                          disabled={actionLoading === run.run_id || run.approval?.state === "rejected"}
                          onClick={() => handleApproval(run.run_id, "reject")}
                        >
                          <ThumbsDown className="mr-1 h-3.5 w-3.5" />驳回
                        </Button>
                        {run.approval?.comment && (
                          <span className="text-xs text-muted-foreground ml-2">
                            备注: {run.approval.comment}
                          </span>
                        )}
                      </div>

                      {/* Sources */}
                      {detail.sources && detail.sources.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                            <Search className="h-4 w-4" />来源溯源 ({detail.sources.length})
                          </h4>
                          <div className="space-y-1.5">
                            {detail.sources.map((s: any, i: number) => (
                              <div key={i} className={cn(
                                "flex items-start gap-2 rounded-lg p-2 text-xs border",
                                s.trusted
                                  ? "bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800"
                                  : "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800"
                              )}>
                                <span className={cn(
                                  "shrink-0 px-1.5 py-0.5 rounded font-medium",
                                  s.trusted ? "bg-green-200 text-green-800" : "bg-amber-200 text-amber-800"
                                )}>
                                  {s.source_id} {s.trusted ? "官方" : "参考"}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <p className="font-medium truncate">{s.title}</p>
                                  {s.excerpt && <p className="text-muted-foreground mt-0.5 line-clamp-2">{s.excerpt}</p>}
                                </div>
                                {s.url && (
                                  <a href={s.url} target="_blank" rel="noopener noreferrer"
                                    className="shrink-0 text-primary hover:underline">
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Verifications */}
                      {detail.verifications && detail.verifications.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                            <Shield className="h-4 w-4" />验证结果 ({detail.verifications.length})
                          </h4>
                          <div className="space-y-1">
                            {detail.verifications.map((v: any, i: number) => (
                              <div key={i} className={cn(
                                "flex items-center gap-2 rounded-lg p-2 text-xs border",
                                v.passed ? "border-green-200 bg-green-50/50" : "border-red-200 bg-red-50/50"
                              )}>
                                {v.passed
                                  ? <CheckCircle className="h-3.5 w-3.5 text-green-600 shrink-0" />
                                  : <XCircle className="h-3.5 w-3.5 text-red-600 shrink-0" />}
                                <span className="font-medium">{v.rule_id}</span>
                                <span className="text-muted-foreground flex-1 truncate">{v.detail}</span>
                                {!v.passed && (
                                  <span className="text-red-600 font-medium">{v.action}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Events timeline */}
                      {detail.events && detail.events.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                            <Clock className="h-4 w-4" />事件时间线 ({detail.events.length})
                          </h4>
                          <div className="space-y-1 max-h-48 overflow-y-auto">
                            {detail.events.map((e: any, i: number) => (
                              <div key={i} className="flex items-center gap-2 text-xs px-2 py-1 rounded bg-muted/50">
                                <span className="font-mono text-muted-foreground w-8 text-right">{e.progress}%</span>
                                <span className="font-medium w-24 truncate">{e.stage}</span>
                                <span className={cn(
                                  "w-16",
                                  e.status === "completed" ? "text-green-600" :
                                  e.status === "running" ? "text-blue-600" : "text-muted-foreground"
                                )}>{e.status}</span>
                                <span className="flex-1 truncate text-muted-foreground">{e.message}</span>
                                {e.duration_ms > 0 && (
                                  <span className="text-muted-foreground">{e.duration_ms}ms</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
