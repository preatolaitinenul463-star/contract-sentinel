"use client";

import { useState, useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { toastError } from "@/lib/toast";
import {
  Upload,
  FileText,
  ArrowRight,
  Plus,
  Minus,
  Edit,
  TrendingUp,
  TrendingDown,
  Minus as Neutral,
  Loader2,
  CheckCircle,
  Clock,
  AlertTriangle,
  Cpu,
  Search,
  FileCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, formatFileSize } from "@/lib/utils";
import { withVisitorHeaders } from "@/lib/api";

interface ChangeItem {
  id: string;
  change_type: "added" | "removed" | "modified";
  clause_type: string;
  original_text?: string;
  new_text?: string;
  risk_impact: "increased" | "decreased" | "neutral" | "uncertain";
  analysis: string;
}

interface AgentStatus {
  name: string;
  icon: any;
  status: "pending" | "running" | "completed" | "error";
  message: string;
  tokens?: number;
}

export default function ComparePage() {
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [changes, setChanges] = useState<ChangeItem[]>([]);
  const [showResult, setShowResult] = useState(false);
  const [progress, setProgress] = useState(0);
  const [summary, setSummary] = useState("");
  const [keyChanges, setKeyChanges] = useState<string[]>([]);
  const [compareStats, setCompareStats] = useState({
    added: 0,
    removed: 0,
    modified: 0,
    risk_increased: 0,
    total: 0,
  });
  const [streamText, setStreamText] = useState("");
  const [currentAgent, setCurrentAgent] = useState("");
  const streamRef = useRef<string>("");

  const [agents, setAgents] = useState<AgentStatus[]>([
    { name: "文档解析", icon: FileCheck, status: "pending", message: "等待开始" },
    { name: "条款结构化", icon: Search, status: "pending", message: "等待开始" },
    { name: "智能对比", icon: Cpu, status: "pending", message: "等待开始" },
  ]);

  const dropzoneA = useDropzone({
    onDrop: (files) => files[0] && setFileA(files[0]),
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 1,
  });

  const dropzoneB = useDropzone({
    onDrop: (files) => files[0] && setFileB(files[0]),
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 1,
  });

  const updateAgent = (agentName: string, updates: Partial<AgentStatus>) => {
    setAgents((prev) =>
      prev.map((a) => (a.name === agentName ? { ...a, ...updates } : a))
    );
  };

  const handleSSEEvent = (data: any) => {
    const {
      stage,
      status,
      progress: p,
      message,
      agent,
      change_item,
      token,
      summary: sum,
      key_changes: kc,
      stats,
      all_changes,
    } = data;

    if (p) setProgress(p);

    // Update agent status
    if (agent) {
      setCurrentAgent(agent);
      if (status === "running") {
        updateAgent(agent, { status: "running", message: message || "" });
      } else if (status === "completed") {
        updateAgent(agent, { status: "completed", message: message || "" });
      } else if (status === "streaming") {
        updateAgent(agent, { status: "running", message: message || "" });
      }
    }

    // 不再展示原始 token 流

    // Found a change
    if (change_item) {
      setChanges((prev) => {
        if (prev.some((c) => c.id === change_item.id)) return prev;
        return [...prev, change_item];
      });
    }

    // Final completion
    if (stage === "complete") {
      if (sum) setSummary(sum);
      if (kc) setKeyChanges(kc);
      if (stats) setCompareStats(stats);
      if (all_changes) setChanges(all_changes);
    }
  };

  const startCompare = async () => {
    if (!fileA || !fileB) return;

    setIsComparing(true);
    setChanges([]);
    setSummary("");
    setKeyChanges([]);
    setStreamText("");
    streamRef.current = "";
    setProgress(0);
    setAgents((prev) =>
      prev.map((a) => ({ ...a, status: "pending", message: a.message.split(" -")[0] }))
    );

    try {
      const formData = new FormData();
      formData.append("file_a", fileA);
      formData.append("file_b", fileB);

      const apiBase = (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) ? "http://localhost:8000/api" : "/api";
      const response = await fetch(`${apiBase}/compare/upload-and-compare`, {
        method: "POST",
        headers: withVisitorHeaders(),
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("No reader");

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              handleSSEEvent(data);
            } catch {}
          }
        }
      }

      setIsComparing(false);
      setShowResult(true);
    } catch (error: any) {
      console.error("Compare failed:", error);
      setIsComparing(false);
      toastError(error.message, "对比失败");
    }
  };

  const changeTypeConfig = {
    added: { icon: Plus, color: "text-green-500", bg: "bg-green-100", label: "新增" },
    removed: { icon: Minus, color: "text-red-500", bg: "bg-red-100", label: "删除" },
    modified: { icon: Edit, color: "text-blue-500", bg: "bg-blue-100", label: "修改" },
  };

  const riskImpactConfig: Record<string, { icon: any; color: string; label: string }> = {
    increased: { icon: TrendingUp, color: "text-red-500", label: "风险上升" },
    decreased: { icon: TrendingDown, color: "text-green-500", label: "风险下降" },
    neutral: { icon: Neutral, color: "text-gray-500", label: "影响中性" },
    uncertain: { icon: AlertTriangle, color: "text-yellow-500", label: "影响不确定" },
  };

  const agentStatusIcon = (s: string) => {
    switch (s) {
      case "running":
        return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "error":
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const renderFileDropzone = (
    file: File | null,
    dropzone: ReturnType<typeof useDropzone>,
    label: string,
    onClear: () => void,
  ) => (
    <div className="flex-1">
      <p className="mb-2 text-sm font-medium">{label}</p>
      {file ? (
        <div className="flex items-center gap-3 rounded-lg border bg-card p-4">
          <FileText className="h-8 w-8 text-primary" />
          <div className="flex-1 min-w-0">
            <p className="truncate font-medium">{file.name}</p>
            <p className="text-sm text-muted-foreground">
              {formatFileSize(file.size)}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClear}>
            移除
          </Button>
        </div>
      ) : (
        <div
          {...dropzone.getRootProps()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
            dropzone.isDragActive
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary"
          )}
        >
          <input {...dropzone.getInputProps()} />
          <Upload className="h-8 w-8 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">
            拖拽或点击上传
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            PDF / DOCX / TXT
          </p>
        </div>
      )}
    </div>
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">合同对比</h1>
        <p className="text-muted-foreground">
          对比两份合同的差异，AI 分析变更带来的风险影响
        </p>
      </div>

      {/* ========== Upload Stage ========== */}
      {!showResult && !isComparing && (
        <div className="space-y-6">
          {/* File Upload */}
          <div className="flex items-center gap-4">
            {renderFileDropzone(fileA, dropzoneA, "原合同", () => setFileA(null))}
            <ArrowRight className="h-6 w-6 text-muted-foreground shrink-0" />
            {renderFileDropzone(fileB, dropzoneB, "新合同", () => setFileB(null))}
          </div>

          {/* Compare Button */}
          <Button
            size="lg"
            className="w-full"
            disabled={!fileA || !fileB}
            onClick={startCompare}
          >
            开始 AI 对比
          </Button>
        </div>
      )}

      {/* ========== Comparing Stage ========== */}
      {isComparing && (
        <div className="space-y-6">
          {/* Agent Pipeline Progress */}
          <div className="rounded-2xl border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">智能对比流水线</h2>
              <span className="text-sm font-medium text-primary">{progress}%</span>
            </div>

            {/* 进度条 */}
            <div className="relative h-2 rounded-full bg-muted overflow-hidden mb-6">
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-primary to-primary/70 transition-all duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
              {progress > 0 && progress < 100 && (
                <div className="absolute inset-y-0 w-8 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-pulse"
                  style={{ left: `${Math.max(0, progress - 5)}%` }} />
              )}
            </div>

            {/* Agent 步骤 */}
            <div className="relative">
              <div className="absolute left-[18px] top-6 bottom-6 w-0.5 bg-muted" />
              <div className="space-y-1">
                {agents.map((agent) => {
                  const Icon = agent.icon;
                  const isActive = agent.status === "running";
                  const isDone = agent.status === "completed";
                  return (
                    <div key={agent.name} className={cn(
                      "relative flex items-center gap-4 rounded-xl px-3 py-3 transition-all duration-300",
                      isActive && "bg-primary/5",
                    )}>
                      <div className={cn(
                        "relative z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 transition-all duration-300",
                        isDone ? "border-green-500 bg-green-500 text-white" :
                        isActive ? "border-primary bg-primary/10 text-primary" :
                        "border-muted bg-background text-muted-foreground"
                      )}>
                        {isDone ? <CheckCircle className="h-4 w-4" /> :
                         isActive ? <Loader2 className="h-4 w-4 animate-spin" /> :
                         <Icon className="h-4 w-4" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={cn("text-sm font-medium", isDone ? "text-green-600" : isActive ? "text-foreground" : "text-muted-foreground")}>{agent.name}</p>
                        <p className="text-xs text-muted-foreground truncate">{agent.message}</p>
                      </div>
                      {isActive && (
                        <div className="flex gap-1">
                          <div className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "0ms" }} />
                          <div className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "150ms" }} />
                          <div className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* 实时发现的差异在下方展示 */}

          {/* Real-time found changes */}
          {changes.length > 0 && (
            <div className="rounded-lg border bg-card p-6">
              <h3 className="text-sm font-semibold mb-3">
                已发现差异 ({changes.length})
              </h3>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {changes.map((change, i) => {
                  const typeConfig = changeTypeConfig[change.change_type];
                  const TypeIcon = typeConfig?.icon || Edit;
                  return (
                    <div
                      key={i}
                      className={cn(
                        "flex items-center gap-2 rounded p-2 text-sm border",
                        typeConfig?.bg || "bg-gray-50"
                      )}
                    >
                      <TypeIcon
                        className={cn(
                          "h-4 w-4 shrink-0",
                          typeConfig?.color || "text-gray-500"
                        )}
                      />
                      <span className="font-medium">{change.clause_type}</span>
                      <span
                        className={cn(
                          "text-xs px-1.5 py-0.5 rounded",
                          typeConfig?.bg,
                          typeConfig?.color
                        )}
                      >
                        {typeConfig?.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========== Result Stage ========== */}
      {showResult && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="rounded-lg border bg-card p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">对比结果</h2>
              <Button
                variant="outline"
                onClick={() => {
                  setShowResult(false);
                  setFileA(null);
                  setFileB(null);
                  setChanges([]);
                  setSummary("");
                  setKeyChanges([]);
                  setStreamText("");
                  streamRef.current = "";
                  setProgress(0);
                  setCompareStats({ added: 0, removed: 0, modified: 0, risk_increased: 0, total: 0 });
                }}
              >
                新对比
              </Button>
            </div>
            <div className="mt-4 flex gap-6">
              <div className="text-center">
                <p className="text-2xl font-bold text-green-500">
                  {compareStats.added}
                </p>
                <p className="text-sm text-muted-foreground">新增条款</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-500">
                  {compareStats.removed}
                </p>
                <p className="text-sm text-muted-foreground">删除条款</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-500">
                  {compareStats.modified}
                </p>
                <p className="text-sm text-muted-foreground">修改条款</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-500">
                  {compareStats.risk_increased}
                </p>
                <p className="text-sm text-muted-foreground">风险上升</p>
              </div>
            </div>

            {/* Summary text */}
            {summary && (
              <div className="mt-4 rounded-lg bg-muted/50 p-4">
                <p className="text-sm font-medium mb-1">AI 总结</p>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {summary}
                </p>
              </div>
            )}

            {/* Key changes */}
            {keyChanges.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium mb-2">关键变更点</p>
                <ul className="space-y-1">
                  {keyChanges.map((kc, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <span className="text-primary font-bold mt-0.5">{i + 1}.</span>
                      {kc}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Changes List */}
          <div className="space-y-4">
            <h3 className="font-semibold">变更详情</h3>
            {changes.map((change) => {
              const typeConfig = changeTypeConfig[change.change_type];
              const riskConfig = riskImpactConfig[change.risk_impact] || riskImpactConfig.neutral;
              const TypeIcon = typeConfig?.icon || Edit;
              const RiskIcon = riskConfig.icon;

              return (
                <div
                  key={change.id}
                  className="rounded-lg border bg-card p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className={cn("rounded p-1", typeConfig?.bg)}>
                      <TypeIcon
                        className={cn("h-4 w-4", typeConfig?.color)}
                      />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {change.clause_type}
                        </span>
                        <span
                          className={cn(
                            "rounded px-2 py-0.5 text-xs",
                            typeConfig?.bg,
                            typeConfig?.color
                          )}
                        >
                          {typeConfig?.label}
                        </span>
                        <span
                          className={cn(
                            "flex items-center gap-1 rounded px-2 py-0.5 text-xs",
                            change.risk_impact === "increased"
                              ? "bg-red-100 text-red-500"
                              : change.risk_impact === "decreased"
                              ? "bg-green-100 text-green-500"
                              : change.risk_impact === "uncertain"
                              ? "bg-yellow-100 text-yellow-500"
                              : "bg-gray-100 text-gray-500"
                          )}
                        >
                          <RiskIcon className="h-3 w-3" />
                          {riskConfig.label}
                        </span>
                      </div>

                      {change.original_text && (
                        <div className="mt-3 rounded bg-red-50 p-3">
                          <p className="text-xs font-medium text-red-600">
                            原文：
                          </p>
                          <p className="mt-1 text-sm line-through text-red-700">
                            {change.original_text}
                          </p>
                        </div>
                      )}

                      {change.new_text && (
                        <div className="mt-2 rounded bg-green-50 p-3">
                          <p className="text-xs font-medium text-green-600">
                            新文：
                          </p>
                          <p className="mt-1 text-sm text-green-700">
                            {change.new_text}
                          </p>
                        </div>
                      )}

                      <p className="mt-3 text-sm text-muted-foreground">
                        <span className="font-medium">分析：</span>
                        {change.analysis}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
