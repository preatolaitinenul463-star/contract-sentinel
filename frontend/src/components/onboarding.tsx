"use client";

import { useState, useEffect } from "react";
import { FileText, Cpu, Download, MessageSquare, X, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

const steps = [
  {
    icon: FileText,
    title: "上传合同",
    description: "支持 PDF、DOCX、TXT 格式，拖拽或点击即可上传",
  },
  {
    icon: Cpu,
    title: "AI 智能审核",
    description: "5 个 AI Agent 流水线自动识别风险条款，实时推送进度",
  },
  {
    icon: Download,
    title: "查看报告",
    description: "审核完成后可查看详细风险报告，支持导出 Word/PDF",
  },
  {
    icon: MessageSquare,
    title: "法律助手",
    description: "有任何法律问题，随时向 AI 法律助手提问",
  },
];

export function Onboarding() {
  const [show, setShow] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const seen = localStorage.getItem("onboarding_seen");
    if (!seen) {
      setShow(true);
    }
  }, []);

  const dismiss = () => {
    setShow(false);
    localStorage.setItem("onboarding_seen", "true");
  };

  if (!show) return null;

  const current = steps[step];
  const Icon = current.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative w-full max-w-md rounded-lg border bg-card p-8 shadow-lg mx-4">
        <button
          onClick={dismiss}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="text-center space-y-4">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Icon className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-xl font-semibold">{current.title}</h3>
          <p className="text-sm text-muted-foreground">{current.description}</p>

          {/* Step indicators */}
          <div className="flex justify-center gap-2">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`h-2 w-2 rounded-full transition-colors ${
                  i === step ? "bg-primary" : "bg-muted"
                }`}
              />
            ))}
          </div>

          <div className="flex gap-3 justify-center pt-2">
            {step < steps.length - 1 ? (
              <>
                <Button variant="outline" size="sm" onClick={dismiss}>
                  跳过
                </Button>
                <Button size="sm" onClick={() => setStep(step + 1)}>
                  下一步 <ArrowRight className="ml-1 h-4 w-4" />
                </Button>
              </>
            ) : (
              <Button onClick={dismiss}>
                开始使用
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
