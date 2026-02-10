"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  FileText,
  CheckCircle,
  Loader2,
  AlertTriangle,
  Play,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toastError, toastSuccess } from "@/lib/toast";
import { cn, formatFileSize } from "@/lib/utils";
import Link from "next/link";

interface QueueItem {
  id: string;
  file: File;
  status: "pending" | "reviewing" | "completed" | "error";
  riskCount?: number;
  reviewId?: number;
  error?: string;
}

export default function BatchReviewPage() {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newItems: QueueItem[] = acceptedFiles.map((file) => ({
      id: Math.random().toString(36).slice(2),
      file,
      status: "pending",
    }));
    setQueue((prev) => [...prev, ...newItems]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 20,
  });

  const removeItem = (id: string) => {
    setQueue((prev) => prev.filter((item) => item.id !== id));
  };

  const startBatchReview = async () => {
    setIsRunning(true);
    const pending = queue.filter((item) => item.status === "pending");

    for (const item of pending) {
      // Update status to reviewing
      setQueue((prev) =>
        prev.map((q) => (q.id === item.id ? { ...q, status: "reviewing" } : q))
      );

      try {
        const formData = new FormData();
        formData.append("file", item.file);
        formData.append("contract_type", "general");
        formData.append("jurisdiction", "CN");
        formData.append("party_role", "party_b");
        formData.append("power_dynamic", "weak");

        const response = await fetch("/api/review/upload-and-review", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        // Read the SSE stream to completion
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let riskCount = 0;
        let reviewId: number | undefined;

        if (reader) {
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
                  if (data.stage === "complete") {
                    riskCount = data.stats?.total || 0;
                    reviewId = data.review_id;
                  }
                } catch {}
              }
            }
          }
        }

        setQueue((prev) =>
          prev.map((q) =>
            q.id === item.id
              ? { ...q, status: "completed", riskCount, reviewId }
              : q
          )
        );
      } catch (error: any) {
        setQueue((prev) =>
          prev.map((q) =>
            q.id === item.id
              ? { ...q, status: "error", error: error.message }
              : q
          )
        );
      }
    }

    setIsRunning(false);
    toastSuccess("批量审核完成");
  };

  const pendingCount = queue.filter((q) => q.status === "pending").length;
  const completedCount = queue.filter((q) => q.status === "completed").length;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">批量合同审核</h1>
        <p className="text-muted-foreground">
          上传多份合同，系统将逐一进行 AI 审核
        </p>
      </div>

      {/* Upload Area */}
      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 transition-colors",
          isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary"
        )}
      >
        <input {...getInputProps()} />
        <Upload className="h-10 w-10 text-muted-foreground" />
        <p className="mt-3 text-sm font-medium">
          {isDragActive ? "放开以上传文件" : "拖拽或点击选择多个合同文件"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">PDF / DOCX / TXT，最多 20 个文件</p>
      </div>

      {/* Queue */}
      {queue.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              共 {queue.length} 个文件 · {completedCount} 已完成 · {pendingCount} 待审核
            </p>
            <Button
              onClick={startBatchReview}
              disabled={isRunning || pendingCount === 0}
            >
              {isRunning ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  审核中...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  开始批量审核
                </>
              )}
            </Button>
          </div>

          <div className="space-y-2">
            {queue.map((item) => (
              <div
                key={item.id}
                className={cn(
                  "flex items-center gap-3 rounded-lg border p-3 transition-colors",
                  item.status === "reviewing" && "border-primary bg-primary/5",
                  item.status === "completed" && "border-green-200 bg-green-50",
                  item.status === "error" && "border-red-200 bg-red-50"
                )}
              >
                {item.status === "completed" ? (
                  <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
                ) : item.status === "reviewing" ? (
                  <Loader2 className="h-5 w-5 animate-spin text-primary shrink-0" />
                ) : item.status === "error" ? (
                  <AlertTriangle className="h-5 w-5 text-red-500 shrink-0" />
                ) : (
                  <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
                )}

                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{item.file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(item.file.size)}
                    {item.status === "completed" && item.riskCount !== undefined && (
                      <span className="ml-2">· 发现 {item.riskCount} 个风险</span>
                    )}
                    {item.status === "error" && (
                      <span className="ml-2 text-red-500">· {item.error}</span>
                    )}
                  </p>
                </div>

                {item.status === "completed" && item.reviewId && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(`/api/review/export/${item.reviewId}?format=docx`, "_blank")}
                  >
                    导出
                  </Button>
                )}

                {item.status === "pending" && (
                  <button
                    onClick={() => removeItem(item.id)}
                    className="text-muted-foreground hover:text-red-500"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Link to single review */}
      <div className="text-center text-sm text-muted-foreground">
        只需审核一份合同？
        <Link href="/review" className="text-primary hover:underline ml-1">
          前往单文件审核
        </Link>
      </div>
    </div>
  );
}
