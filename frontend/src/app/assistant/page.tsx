"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send, Bot, User, Loader2, Plus, MessageSquare, Trash2,
  ExternalLink, Paperclip, FileText, X, Globe, Search,
  Lock, Download, Scale, Briefcase, FileEdit, HelpCircle,
  AlertTriangle, CheckCircle, Shield,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "@/components/markdown-content";
import { withVisitorHeaders } from "@/lib/api";

const API_BASE =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000/api"
    : "/api";

interface Source {
  source_id: string;
  trusted: boolean;
  kind: string;
  title: string;
  url?: string;
  excerpt?: string;
  institution?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  statusMessage?: string;
  sources?: Source[];
  reportJson?: any;
  structured?: boolean;
  verificationDecision?: string;
  runId?: string;
  fileName?: string;
  mode?: string;
  policySource?: string;
  policyVersion?: string;
}

interface Session {
  id: number;
  title: string;
  message_count: number;
  updated_at: string | null;
}

const MODES = [
  { id: "qa", label: "法律问答", icon: HelpCircle, desc: "解答法律问题" },
  { id: "case_analysis", label: "案件分析", icon: Scale, desc: "案情深度分析" },
  { id: "contract_review", label: "合同审查", icon: FileText, desc: "条款风险识别" },
  { id: "doc_draft", label: "文书起草", icon: FileEdit, desc: "法律文书辅助" },
];

const WELCOME_MESSAGE: Message = {
  id: "welcome", role: "assistant",
  content: `您好，我是合同哨兵的**法律助手**。请选择上方模式开始：

- **法律问答** — 解答各类法律问题，引用具体法条
- **案件分析** — 分析案情，梳理法律关系与胜诉可能性
- **合同审查** — 审查合同条款，识别法律风险
- **文书起草** — 辅助起草法律意见书、答辩状等

支持上传 PDF / Word / 图片文件。所有结论均附来源引用。`,
  timestamp: new Date(),
};

export default function AssistantPage() {
  const { token, isAuthenticated } = useAuthStore();
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [selectedMode, setSelectedMode] = useState("qa");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(() => { scrollToBottom(); }, [messages]);
  useEffect(() => { if (isAuthenticated && token) loadSessions(); }, [isAuthenticated, token]);

  const loadSessions = async () => {
    if (!token) return;
    setSessionsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/assistant/sessions`, { headers: withVisitorHeaders({ Authorization: `Bearer ${token}` }) });
      if (res.ok) setSessions(await res.json());
    } catch (e) { console.error("Load sessions failed:", e); }
    finally { setSessionsLoading(false); }
  };

  const loadSessionMessages = async (sessionId: number) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/assistant/sessions/${sessionId}/messages`, { headers: withVisitorHeaders({ Authorization: `Bearer ${token}` }) });
      if (res.ok) {
        const data = await res.json();
        const loaded: Message[] = data.map((m: any) => ({
          id: m.id.toString(), role: m.role, content: m.content,
          timestamp: new Date(m.created_at), sources: m.citations,
        }));
        setMessages(loaded.length > 0 ? loaded : [WELCOME_MESSAGE]);
        setCurrentSessionId(sessionId);
      }
    } catch (e) { console.error("Load messages failed:", e); }
  };

  const startNewChat = () => { setMessages([WELCOME_MESSAGE]); setCurrentSessionId(null); setAttachedFile(null); };
  const deleteSession = async (sessionId: number) => {
    if (!token) return;
    try {
      await fetch(`${API_BASE}/assistant/sessions/${sessionId}`, { method: "DELETE", headers: withVisitorHeaders({ Authorization: `Bearer ${token}` }) });
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) startNewChat();
    } catch (e) { console.error("Delete session failed:", e); }
  };

  const sendMessage = async () => {
    if ((!input.trim() && !attachedFile) || isLoading) return;
    const messageText = input.trim() || (attachedFile ? `请分析这个文件：${attachedFile.name}` : "");
    const userMessage: Message = {
      id: Date.now().toString(), role: "user", content: messageText,
      timestamp: new Date(), fileName: attachedFile?.name, mode: selectedMode,
    };
    const assistantId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantId, role: "assistant", content: "", timestamp: new Date(), isStreaming: true,
    };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput(""); setIsLoading(true);

    try {
      let response: Response;
      if (attachedFile) {
        const formData = new FormData();
        formData.append("message", messageText);
        formData.append("mode", selectedMode);
        formData.append("file", attachedFile);
        if (currentSessionId) formData.append("session_id", currentSessionId.toString());
        response = await fetch(`${API_BASE}/assistant/chat/upload`, {
          method: "POST", body: formData,
          headers: withVisitorHeaders(token ? { Authorization: `Bearer ${token}` } : {}),
        });
        setAttachedFile(null);
      } else {
        let url = `${API_BASE}/assistant/chat/stream?message=${encodeURIComponent(messageText)}&mode=${selectedMode}`;
        if (currentSessionId) url += `&session_id=${currentSessionId}`;
        if (token) url += `&token=${encodeURIComponent(token)}`;
        response = await fetch(url, { headers: withVisitorHeaders() });
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No reader");
      let buffer = ""; let fullContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n"); buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "status") {
              setMessages((prev) => prev.map((m) =>
                m.id === assistantId ? { ...m, statusMessage: data.message } : m
              ));
            } else if (data.type === "token") {
              fullContent += data.content;
              setMessages((prev) => prev.map((m) =>
                m.id === assistantId ? { ...m, content: fullContent, statusMessage: undefined } : m
              ));
            } else if (data.type === "done") {
              setMessages((prev) => prev.map((m) =>
                m.id === assistantId ? {
                  ...m, content: data.full_content || fullContent, isStreaming: false,
                  sources: data.sources, reportJson: data.report_json,
                  structured: data.structured, verificationDecision: data.verification_decision,
                  runId: data.run_id, statusMessage: undefined, mode: selectedMode,
                  policySource: data.policy_source, policyVersion: data.policy_version,
                } : m
              ));
              if (data.session_id && !currentSessionId) setCurrentSessionId(data.session_id);
              if (isAuthenticated) loadSessions();
            } else if (data.type === "error") {
              setMessages((prev) => prev.map((m) =>
                m.id === assistantId ? { ...m, content: `错误: ${data.error}`, isStreaming: false, statusMessage: undefined } : m
              ));
            }
          } catch {}
        }
      }
      setMessages((prev) => prev.map((m) =>
        m.id === assistantId ? { ...m, isStreaming: false, statusMessage: undefined } : m
      ));
    } catch (error: any) {
      setMessages((prev) => prev.map((m) =>
        m.id === assistantId ? { ...m, content: `连接失败: ${error.message}`, isStreaming: false, statusMessage: undefined } : m
      ));
    } finally { setIsLoading(false); }
  };

  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  const renderSourceCards = (sources: Source[]) => (
    <div className="mt-2 pt-2 border-t border-border/30">
      <button
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setSourcesExpanded(!sourcesExpanded)}
      >
        <Search className="h-3 w-3" />
        <span>来源引用 ({sources.length})</span>
        <span className="ml-1">{sourcesExpanded ? "▲" : "▼"}</span>
      </button>
      {sourcesExpanded && (
        <div className="mt-1.5 space-y-1">
          {sources.map((s, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={cn(
                "shrink-0 px-1 py-0.5 rounded text-[10px] font-medium",
                s.trusted ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                          : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
              )}>
                {s.source_id}{s.trusted ? "官方" : "参考"}
              </span>
              <span className="truncate flex-1">{s.title}</span>
              {s.url && (
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-primary hover:underline">
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderVerificationBadge = (decision: string | undefined) => {
    if (!decision) return null;
    if (decision === "pass") return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
        <CheckCircle className="h-3 w-3" />验证通过
      </span>
    );
    if (decision === "degrade_with_disclaimer") return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
        <AlertTriangle className="h-3 w-3" />部分降级
      </span>
    );
    if (decision === "human_review_required") return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
        <Shield className="h-3 w-3" />待人工复核
      </span>
    );
    return null;
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* 会话侧边栏 - 桌面端显示 */}
      {isAuthenticated && (
        <div className="hidden md:flex w-56 shrink-0 rounded-2xl border bg-card p-3 flex-col shadow-sm">
          <Button size="sm" className="w-full mb-3" onClick={startNewChat}>
            <Plus className="mr-2 h-4 w-4" />新建对话
          </Button>
          <div className="flex-1 overflow-y-auto space-y-1">
            {sessionsLoading ? (
              <div className="flex items-center justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
            ) : sessions.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">暂无历史对话</p>
            ) : (
              sessions.map((session) => (
                <div key={session.id} className={cn(
                  "group flex items-center gap-2 rounded-lg px-2 py-1.5 cursor-pointer text-sm transition-colors",
                  currentSessionId === session.id ? "bg-primary/10 text-primary" : "hover:bg-accent text-muted-foreground"
                )} onClick={() => loadSessionMessages(session.id)}>
                  <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                  <span className="flex-1 truncate">{session.title}</span>
                  <button className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}>
                    <Trash2 className="h-3 w-3 text-muted-foreground hover:text-red-500" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 聊天区域 */}
      <div className="flex flex-1 flex-col min-w-0">
        <div className="mb-3">
          <h1 className="text-xl md:text-2xl font-bold">法律助手</h1>
          <p className="text-sm md:text-base text-muted-foreground">
            智能法律问答 · 案件分析 · 法规检索 · 文件解析
          </p>
        </div>

        {/* 模式选择 - 手机端可滚动 */}
        <div className="flex gap-2 mb-3 overflow-x-auto pb-1 scrollbar-hide">
          {MODES.map((mode) => {
            const Icon = mode.icon;
            return (
              <button key={mode.id}
                className={cn(
                  "flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium transition-all border whitespace-nowrap",
                  selectedMode === mode.id
                    ? "bg-primary text-primary-foreground border-primary shadow-sm"
                    : "bg-card text-muted-foreground border-border hover:bg-accent hover:text-foreground"
                )}
                onClick={() => setSelectedMode(mode.id)}
              >
                <Icon className="h-4 w-4" />
                {mode.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-1 flex-col rounded-2xl border bg-card overflow-hidden shadow-sm">
          {/* 消息列表 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => (
              <div key={message.id} className={cn("flex gap-3", message.role === "user" ? "justify-end" : "justify-start")}>
                {message.role === "assistant" && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <Bot className="h-4 w-4" />
                  </div>
                )}
                <div className={cn("max-w-[80%] rounded-2xl p-4", message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted")}>
                  {message.fileName && (
                    <div className="flex items-center gap-1.5 mb-2 text-xs opacity-80">
                      <FileText className="h-3 w-3" /><span>{message.fileName}</span>
                    </div>
                  )}
                  {message.statusMessage && !message.content && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Globe className="h-4 w-4 animate-pulse text-primary" />{message.statusMessage}
                    </div>
                  )}
                  {message.content && (
                    <div>
                      {message.role === "assistant" ? (
                        <MarkdownContent content={message.content} />
                      ) : (
                        <p className="whitespace-pre-wrap text-[15px] md:text-base leading-relaxed">{message.content}</p>
                      )}
                      {message.isStreaming && (
                        <span className="inline-block w-1.5 h-4 bg-primary ml-0.5 animate-pulse rounded-sm" />
                      )}
                    </div>
                  )}
                  {/* Verification badge + export */}
                  {message.role === "assistant" && !message.isStreaming && message.verificationDecision && (
                    <div className="flex items-center gap-2 mt-2">
                      {renderVerificationBadge(message.verificationDecision)}
                      {message.policySource && (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                          策略: {message.policySource === "user" ? "用户标准" : "系统默认"}
                        </span>
                      )}
                      {message.runId && (
                        <Button variant="ghost" size="sm" className="h-6 text-xs px-2"
                          onClick={() => window.open(`${API_BASE}/assistant/export/${message.runId}?format=docx`, "_blank")}>
                          <Download className="h-3 w-3 mr-1" />Word
                        </Button>
                      )}
                    </div>
                  )}
                  {/* Source cards */}
                  {message.sources && message.sources.length > 0 && renderSourceCards(message.sources)}
                </div>
                {message.role === "user" && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))}
            {isLoading && messages[messages.length - 1]?.content === "" && !messages[messages.length - 1]?.statusMessage && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="rounded-2xl bg-muted p-4"><Loader2 className="h-4 w-4 animate-spin text-primary" /></div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 附件预览 */}
          {attachedFile && (
            <div className="mx-4 mb-2 flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2">
              <FileText className="h-4 w-4 text-primary shrink-0" />
              <span className="text-sm truncate flex-1">{attachedFile.name}</span>
              <button onClick={() => setAttachedFile(null)} className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
            </div>
          )}

          {/* 输入区域 */}
          <div className="border-t p-4">
            <div className="flex gap-2 items-end">
              <input ref={fileInputRef} type="file" accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg,.gif,.webp" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setAttachedFile(f); e.target.value = ""; }} />
              <Button variant="ghost" size="icon" className="shrink-0 h-10 w-10"
                onClick={() => fileInputRef.current?.click()} disabled={isLoading} title="上传文件">
                <Paperclip className="h-5 w-5" />
              </Button>
              <input type="text" value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
                placeholder="输入法律问题、案件描述..." disabled={isLoading}
                className="flex-1 rounded-xl border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <Button onClick={sendMessage} disabled={(!input.trim() && !attachedFile) || isLoading} className="shrink-0 h-10 w-10" size="icon">
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              支持 PDF / Word / 图片 · 联网检索最新法规 · 官方来源优先 · 结论附脚注引用
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
