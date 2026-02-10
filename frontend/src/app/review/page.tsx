"use client";

import { useState, useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { toastError, toastSuccess } from "@/lib/toast";
import {
  Upload,
  FileText,
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  Cpu,
  Shield,
  Search,
  PenTool,
  FileCheck,
  Loader2,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, formatFileSize } from "@/lib/utils";

type ReviewStage = "upload" | "reviewing" | "complete";
type ReviewMode = "review" | "redline";

interface RiskItem {
  id: string;
  severity: "high" | "medium" | "low";
  name: string;
  description: string;
  clause_text: string;
  suggestion?: string;
  legal_basis?: string;
  source?: string;
}

interface AgentStatus {
  name: string;
  icon: any;
  status: "pending" | "running" | "completed" | "error";
  message: string;
  detail?: string;
  tokens?: number;
}

interface RedlineItem {
  risk_name: string;
  original: string;
  modified: string;
  reason: string;
}

const REVIEW_AGENTS: AgentStatus[] = [
  { name: "文档解析", icon: FileCheck, status: "pending", message: "等待开始" },
  { name: "条款结构化", icon: Search, status: "pending", message: "等待开始" },
  { name: "规则预筛", icon: Shield, status: "pending", message: "等待开始" },
  { name: "法规检索", icon: Search, status: "pending", message: "等待开始" },
  { name: "深度审核", icon: Cpu, status: "pending", message: "等待开始" },
  { name: "修改建议", icon: PenTool, status: "pending", message: "等待开始" },
];

const REDLINE_AGENTS: AgentStatus[] = [
  { name: "文档解析", icon: FileCheck, status: "pending", message: "等待开始" },
  { name: "条款结构化", icon: Search, status: "pending", message: "等待开始" },
  { name: "规则预筛", icon: Shield, status: "pending", message: "等待开始" },
  { name: "法规检索", icon: Search, status: "pending", message: "等待开始" },
  { name: "深度审核", icon: Cpu, status: "pending", message: "等待开始" },
  { name: "文档批注", icon: PenTool, status: "pending", message: "等待开始" },
];

const API_BASE =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000/api"
    : "/api";

export default function ReviewPage() {
  const [stage, setStage] = useState<ReviewStage>("upload");
  const [mode, setMode] = useState<ReviewMode>("review");
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [riskItems, setRiskItems] = useState<RiskItem[]>([]);
  const [redlines, setRedlines] = useState<RedlineItem[]>([]);
  const [contractType, setContractType] = useState("general");
  const [jurisdiction, setJurisdiction] = useState("CN");
  const [partyRole, setPartyRole] = useState("party_b");
  const [powerDynamic, setPowerDynamic] = useState("weak");
  const [summary, setSummary] = useState("");
  const [stats, setStats] = useState({ high: 0, medium: 0, low: 0, total: 0 });
  const [streamText, setStreamText] = useState("");
  const [reviewId, setReviewId] = useState<number | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloadName, setDownloadName] = useState<string | null>(null);
  const [expandedRisk, setExpandedRisk] = useState<number | null>(null);
  const streamRef = useRef<string>("");

  const [agents, setAgents] = useState<AgentStatus[]>(REVIEW_AGENTS.map((a) => ({ ...a })));

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) setFile(acceptedFiles[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
  });

  const updateAgent = (agentName: string, updates: Partial<AgentStatus>) => {
    setAgents((prev) =>
      prev.map((a) => (a.name === agentName ? { ...a, ...updates } : a))
    );
  };

  const handleSSEEvent = (data: any) => {
    const { stage: eventStage, status, progress: p, message, agent, risk_item, redline, token, summary: sum, stats: st, all_risks } = data;
    if (p) setProgress(p);

    if (agent) {
      if (status === "running" || status === "streaming") {
        updateAgent(agent, { status: "running", message: message || "" });
      } else if (status === "completed") {
        updateAgent(agent, { status: "completed", message: message || "" });
      }
    }

    // 流式文本（只在深度审核阶段展示）
    if (token && (eventStage === "llm_review" || status === "streaming")) {
      streamRef.current += token;
      setStreamText(streamRef.current);
    }

    if (risk_item) {
      setRiskItems((prev) => {
        if (prev.some((r) => r.name === risk_item.name)) return prev;
        return [...prev, risk_item];
      });
    }

    if (redline) setRedlines((prev) => [...prev, redline]);

    if (eventStage === "complete" || eventStage === "error") {
      if (sum) setSummary(sum);
      if (st) setStats(st);
      if (all_risks) setRiskItems(all_risks);
      if (data.review_id) setReviewId(data.review_id);
      if (data.download_url) setDownloadUrl(data.download_url);
      if (data.download_name) setDownloadName(data.download_name);
    }
  };

  const runSSEStream = async (url: string) => {
    const formData = new FormData();
    formData.append("file", file!);
    formData.append("contract_type", contractType);
    formData.append("jurisdiction", jurisdiction);
    formData.append("party_role", partyRole);
    formData.append("power_dynamic", powerDynamic);

    const response = await fetch(url, { method: "POST", body: formData });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

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
          try { handleSSEEvent(JSON.parse(line.slice(6))); } catch {}
        }
      }
    }
  };

  const resetState = () => {
    setRiskItems([]);
    setRedlines([]);
    setStreamText("");
    streamRef.current = "";
    setProgress(0);
    setReviewId(null);
    setDownloadUrl(null);
    setDownloadName(null);
    setExpandedRisk(null);
    setSummary("");
    setStats({ high: 0, medium: 0, low: 0, total: 0 });
  };

  // 从已收集的 riskItems 计算统计（容错，防止 complete 事件未被接收）
  const computeStatsFromRisks = () => {
    setStats((prev) => {
      // 只在 stats 全为 0 时才从 riskItems 推算
      if (prev.total > 0) return prev;
      return {
        high: riskItems.filter((r) => r.severity === "high").length,
        medium: riskItems.filter((r) => r.severity === "medium").length,
        low: riskItems.filter((r) => r.severity === "low").length,
        total: riskItems.length,
      };
    });
  };

  const startReview = async () => {
    if (!file) return;
    setMode("review");
    setStage("reviewing");
    resetState();
    setAgents(REVIEW_AGENTS.map((a) => ({ ...a })));
    try {
      await runSSEStream(`${API_BASE}/review/upload-and-review`);
    } catch (error: any) {
      setStage("upload");
      toastError(error.message, "审核失败");
      return;
    }
    // 流结束后，容错计算 stats
    setTimeout(() => computeStatsFromRisks(), 100);
    setStage("complete");
  };

  const startRedline = async () => {
    if (!file) return;
    setMode("redline");
    setStage("reviewing");
    resetState();
    setAgents(REDLINE_AGENTS.map((a) => ({ ...a })));
    try {
      await runSSEStream(`${API_BASE}/review/redline`);
    } catch (error: any) {
      setStage("upload");
      toastError(error.message, "批阅失败");
      return;
    }
    setTimeout(() => computeStatsFromRisks(), 100);
    setStage("complete");
  };

  const severityConfig = {
    high: { color: "text-red-600", bg: "bg-red-50 dark:bg-red-950/30", label: "高风险", border: "border-red-200 dark:border-red-800", dot: "bg-red-500" },
    medium: { color: "text-amber-600", bg: "bg-amber-50 dark:bg-amber-950/30", label: "中风险", border: "border-amber-200 dark:border-amber-800", dot: "bg-amber-500" },
    low: { color: "text-blue-600", bg: "bg-blue-50 dark:bg-blue-950/30", label: "低风险", border: "border-blue-200 dark:border-blue-800", dot: "bg-blue-500" },
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">合同审核</h1>
        <p className="text-muted-foreground">上传合同文件，智能流水线自动识别风险条款并提供修改建议</p>
      </div>

      {/* ========== 上传阶段 ========== */}
      {stage === "upload" && (
        <div className="space-y-6">
          {/* 上传区域 */}
          <div
            {...getRootProps()}
            className={cn(
              "relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 transition-all duration-200",
              isDragActive
                ? "border-primary bg-primary/5 scale-[1.01]"
                : "border-muted-foreground/25 hover:border-primary hover:bg-accent/50"
            )}
          >
            <input {...getInputProps()} />
            <div className="rounded-2xl bg-primary/10 p-4 mb-4">
              <Upload className="h-8 w-8 text-primary" />
            </div>
            <p className="text-lg font-medium">{isDragActive ? "放开以上传文件" : "拖拽文件到此处，或点击选择"}</p>
            <p className="mt-1 text-sm text-muted-foreground">支持 PDF、DOCX、TXT，最大 50MB</p>
          </div>

          {/* 已选文件 */}
          {file && (
            <div className="flex items-center gap-4 rounded-xl border bg-card p-4 shadow-sm">
              <div className="rounded-lg bg-primary/10 p-2.5">
                <FileText className="h-6 w-6 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{file.name}</p>
                <p className="text-sm text-muted-foreground">{formatFileSize(file.size)}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setFile(null)}>移除</Button>
            </div>
          )}

          {/* 审核选项 */}
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium">合同类型</label>
              <select value={contractType} onChange={(e) => setContractType(e.target.value)}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2.5 text-sm">
                <option value="general">通用商事合同</option>
                <option value="labor">劳动合同</option>
                <option value="tech">技术/软件合同</option>
                <option value="sales">买卖合同</option>
                <option value="lease">租赁合同</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">适用法域</label>
              <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2.5 text-sm">
                <option value="CN">中国大陆</option>
                <option value="HK">香港</option>
                <option value="SG">新加坡</option>
                <option value="US">美国</option>
                <option value="UK">英国</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">我方身份</label>
              <select value={partyRole} onChange={(e) => setPartyRole(e.target.value)}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2.5 text-sm">
                <option value="party_a">甲方（发起方/采购方）</option>
                <option value="party_b">乙方（供应方/服务方）</option>
                <option value="third_party">第三方独立审核</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">谈判地位</label>
              <select value={powerDynamic} onChange={(e) => setPowerDynamic(e.target.value)}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2.5 text-sm">
                <option value="strong">强势方（大厂/大客户）</option>
                <option value="weak">弱势方（小供应商）</option>
                <option value="equal">对等谈判</option>
              </select>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-3">
            <Button size="lg" className="flex-1 h-12 text-base" disabled={!file} onClick={startReview}>
              <Sparkles className="mr-2 h-5 w-5" />
              智能审核
            </Button>
            <Button
              size="lg" variant="outline"
              className="flex-1 h-12 text-base"
              disabled={!file || !file.name.endsWith(".docx")}
              onClick={startRedline}
            >
              <PenTool className="mr-2 h-5 w-5" />
              批阅模式
            </Button>
          </div>
          {file && !file.name.endsWith(".docx") && (
            <p className="text-xs text-muted-foreground text-center -mt-2">批阅模式仅支持 .docx 格式</p>
          )}
        </div>
      )}

      {/* ========== 审核进行中 ========== */}
      {stage === "reviewing" && (
        <div className="space-y-5">
          {/* 流水线卡片 */}
          <div className="rounded-2xl border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">
                {mode === "redline" ? "批阅流水线" : "智能审核流水线"}
              </h2>
              <span className="text-sm font-medium text-primary">{progress}%</span>
            </div>

            {/* 精美进度条 */}
            <div className="relative h-2 rounded-full bg-muted overflow-hidden mb-6">
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-primary to-primary/70 transition-all duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
              {progress > 0 && progress < 100 && (
                <div
                  className="absolute inset-y-0 w-8 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-pulse"
                  style={{ left: `${Math.max(0, progress - 5)}%` }}
                />
              )}
            </div>

            {/* Agent 步骤 */}
            <div className="relative">
              {/* 连接线 */}
              <div className="absolute left-[18px] top-6 bottom-6 w-0.5 bg-muted" />
              <div className="space-y-1">
                {agents.map((agent, i) => {
                  const Icon = agent.icon;
                  const isActive = agent.status === "running";
                  const isDone = agent.status === "completed";
                  return (
                    <div key={agent.name} className={cn(
                      "relative flex items-center gap-4 rounded-xl px-3 py-3 transition-all duration-300",
                      isActive && "bg-primary/5",
                    )}>
                      {/* 状态圆点 */}
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
                        <p className={cn(
                          "text-sm font-medium transition-colors",
                          isDone ? "text-green-600" : isActive ? "text-foreground" : "text-muted-foreground"
                        )}>{agent.name}</p>
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

          {/* 深度审核实时输出 */}
          {streamText && (
            <div className="rounded-2xl border bg-card p-5 shadow-sm">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                深度分析中
              </h3>
              <div className="max-h-48 overflow-y-auto rounded-lg bg-muted/30 p-4">
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/80">{streamText.slice(-800)}</p>
              </div>
            </div>
          )}

          {/* 实时风险发现 */}
          {riskItems.length > 0 && (
            <div className="rounded-2xl border bg-card p-5 shadow-sm">
              <h3 className="text-sm font-semibold mb-3">已发现风险 ({riskItems.length})</h3>
              <div className="space-y-2 max-h-52 overflow-y-auto">
                {riskItems.map((item, i) => {
                  const sev = severityConfig[item.severity] || severityConfig.medium;
                  return (
                    <div key={i} className={cn("flex items-center gap-3 rounded-lg p-2.5 border", sev.border, sev.bg)}>
                      <div className={cn("h-2.5 w-2.5 rounded-full shrink-0", sev.dot)} />
                      <span className="text-sm font-medium flex-1 truncate">{item.name}</span>
                      <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", sev.bg, sev.color)}>{sev.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========== 审核完成 ========== */}
      {stage === "complete" && (
        <div className="space-y-5">
          {/* 顶部摘要卡 */}
          <div className="rounded-2xl border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold">{mode === "redline" ? "批阅完成" : "审核完成"}</h2>
                <p className="text-sm text-muted-foreground mt-0.5">{file?.name}</p>
              </div>
              <div className="flex gap-2">
                {mode === "redline" ? (
                  <Button
                    disabled={!downloadUrl}
                    onClick={() => {
                      if (!downloadUrl) return;
                      const dlName = downloadName || `${file?.name?.replace(/\.\w+$/, "")}_批注版.docx`;
                      const base = `${API_BASE}${downloadUrl.replace("/api", "")}`;
                      const url = `${base}?name=${encodeURIComponent(dlName)}`;
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = dlName;
                      a.click();
                      toastSuccess("批注版已开始下载");
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />下载批注版 Word
                  </Button>
                ) : reviewId ? (
                  <>
                    <Button variant="outline" size="sm"
                      onClick={() => {
                        const url = `${API_BASE}/review/export/${reviewId}?format=docx`;
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${file?.name?.replace(/\.\w+$/, "") || "合同"}_审核报告.docx`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                      }}>
                      <Download className="mr-2 h-4 w-4" />Word
                    </Button>
                    <Button variant="outline" size="sm"
                      onClick={() => {
                        const url = `${API_BASE}/review/export/${reviewId}?format=pdf`;
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${file?.name?.replace(/\.\w+$/, "") || "合同"}_审核报告.pdf`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                      }}>
                      <Download className="mr-2 h-4 w-4" />PDF
                    </Button>
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground">保存中，请稍后刷新</span>
                )}
              </div>
            </div>

            {/* 统计数字 */}
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl bg-red-50 dark:bg-red-950/30 p-4 text-center">
                <p className="text-3xl font-bold text-red-600">{stats.high}</p>
                <p className="text-xs text-red-600/80 mt-1">高风险</p>
              </div>
              <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 p-4 text-center">
                <p className="text-3xl font-bold text-amber-600">{stats.medium}</p>
                <p className="text-xs text-amber-600/80 mt-1">中风险</p>
              </div>
              <div className="rounded-xl bg-blue-50 dark:bg-blue-950/30 p-4 text-center">
                <p className="text-3xl font-bold text-blue-600">{stats.low}</p>
                <p className="text-xs text-blue-600/80 mt-1">低风险</p>
              </div>
            </div>

            {summary && (
              <div className="mt-4 rounded-xl bg-muted/50 p-4">
                <p className="text-sm font-medium mb-1.5">总结</p>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">{summary}</p>
              </div>
            )}
          </div>

          {/* 风险详情（可展开） */}
          <div className="space-y-3">
            <h3 className="font-semibold">风险条款详情 ({riskItems.length})</h3>
            {riskItems.map((item, i) => {
              const sev = severityConfig[item.severity] || severityConfig.medium;
              const isExpanded = expandedRisk === i;
              return (
                <div key={i} className={cn("rounded-xl border transition-all", sev.border, isExpanded && sev.bg)}>
                  {/* 标题行 - 可点击展开 */}
                  <button
                    className="w-full flex items-center gap-3 p-4 text-left"
                    onClick={() => setExpandedRisk(isExpanded ? null : i)}
                  >
                    <div className={cn("h-3 w-3 rounded-full shrink-0", sev.dot)} />
                    <span className="font-medium text-sm flex-1">{item.name}</span>
                    <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", sev.bg, sev.color)}>{sev.label}</span>
                    {item.source && (
                      <span className="text-xs text-muted-foreground">{item.source === "rule_engine" ? "规则" : "AI"}</span>
                    )}
                    {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                  </button>

                  {/* 展开详情 */}
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-3">
                      <p className="text-sm text-muted-foreground">{item.description}</p>
                      {item.clause_text && (
                        <div className="rounded-lg bg-muted p-3">
                          <p className="text-xs font-medium mb-1">原文条款</p>
                          <p className="text-sm">{item.clause_text}</p>
                        </div>
                      )}
                      {item.suggestion && (
                        <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3">
                          <p className="text-xs font-medium text-green-700 dark:text-green-400 mb-1">修改建议</p>
                          <p className="text-sm text-green-700 dark:text-green-300">{item.suggestion}</p>
                        </div>
                      )}
                      {item.legal_basis && (
                        <p className="text-xs text-muted-foreground">法律依据: {item.legal_basis}</p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Redlines */}
          {redlines.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-semibold">修改建议对照</h3>
              {redlines.map((rl, i) => (
                <div key={i} className="rounded-xl border bg-card p-4">
                  <p className="font-medium text-sm mb-3">{rl.risk_name}</p>
                  <div className="grid md:grid-cols-2 gap-3">
                    <div className="rounded-lg bg-red-50 dark:bg-red-950/30 p-3">
                      <p className="text-xs font-medium text-red-600 mb-1">原文</p>
                      <p className="text-sm line-through text-red-700 dark:text-red-400">{rl.original}</p>
                    </div>
                    <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3">
                      <p className="text-xs font-medium text-green-600 mb-1">修改后</p>
                      <p className="text-sm text-green-700 dark:text-green-400">{rl.modified}</p>
                    </div>
                  </div>
                  {rl.reason && <p className="mt-2 text-xs text-muted-foreground">理由: {rl.reason}</p>}
                </div>
              ))}
            </div>
          )}

          {/* 底部操作 */}
          <Button variant="outline" onClick={() => {
            setStage("upload");
            setFile(null);
            resetState();
          }}>
            审核新合同
          </Button>
        </div>
      )}
    </div>
  );
}
