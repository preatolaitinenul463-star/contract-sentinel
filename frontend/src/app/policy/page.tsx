"use client";

import { useEffect, useState } from "react";
import { FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";
import { policyApi } from "@/lib/api";
import { toastError, toastSuccess } from "@/lib/toast";

export default function PolicyPage() {
  const { token } = useAuthStore();
  const [policyText, setPolicyText] = useState("");
  const [policyFileName, setPolicyFileName] = useState("");
  const [policyPreview, setPolicyPreview] = useState<any>(null);
  const [policyWarnings, setPolicyWarnings] = useState<string[]>([]);
  const [preferUserStandard, setPreferUserStandard] = useState(true);
  const [fallbackToDefault, setFallbackToDefault] = useState(true);
  const [loading, setLoading] = useState(false);

  const loadPolicy = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data: any = await policyApi.getMyPolicy(token, "general", "CN");
      setPolicyWarnings(data.parse_warnings || []);
      setPreferUserStandard(Boolean(data.prefer_user_standard ?? true));
      setFallbackToDefault(Boolean(data.fallback_to_default ?? true));
      if (data.source === "user") {
        setPolicyPreview({
          must_review_items: data.must_review_items,
          forbidden_terms: data.forbidden_terms,
          risk_tolerance: data.risk_tolerance,
        });
      } else {
        setPolicyPreview(null);
      }
    } catch {
      toastError("加载审核标准失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicy();
  }, [token]);

  const handlePolicyFile = async (file: File) => {
    setPolicyFileName(file.name);
    try {
      const text = await file.text();
      setPolicyText(text.slice(0, 30000));
      toastSuccess("已读取文件内容，可先点“解析预览”");
    } catch {
      toastError("文件读取失败，请改为粘贴文本");
    }
  };

  const previewPolicy = async () => {
    if (!token || !policyText.trim()) return;
    setLoading(true);
    try {
      const data: any = await policyApi.parsePreview(token, policyText);
      setPolicyPreview(data.parsed_policy);
      setPolicyWarnings(data.parse_warnings || []);
      toastSuccess(`解析完成（成功度 ${(data.success_score * 100).toFixed(0)}%）`);
    } catch (error: any) {
      toastError(error.message || "解析失败");
    } finally {
      setLoading(false);
    }
  };

  const savePolicy = async () => {
    if (!token) return;
    setLoading(true);
    try {
      await policyApi.updateMyPolicy(token, {
        standard_text: policyText,
        prefer_user_standard: preferUserStandard,
        fallback_to_default: fallbackToDefault,
      });
      toastSuccess("审核标准已保存");
      await loadPolicy();
    } catch (error: any) {
      toastError(error.message || "保存失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">审核标准</h1>
        <p className="text-muted-foreground">上传或粘贴贵司/个人审核手册，系统将优先按您的规则审核。</p>
      </div>

      <div className="rounded-xl border bg-card p-6 space-y-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <FileText className="h-4 w-4" />
          支持 .txt / .md / .csv / .json
        </div>
        <div className="flex items-center gap-2">
          <input
            type="file"
            accept=".txt,.md,.csv,.json"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handlePolicyFile(file);
              e.currentTarget.value = "";
            }}
            className="text-sm"
          />
          {policyFileName && <span className="text-xs text-muted-foreground">已加载：{policyFileName}</span>}
        </div>
        <textarea
          value={policyText}
          onChange={(e) => setPolicyText(e.target.value)}
          rows={12}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          placeholder="粘贴您的审核标准，例如：预付款比例、账期上限、违约责任、争议解决地等。"
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={preferUserStandard}
              onChange={(e) => setPreferUserStandard(e.target.checked)}
            />
            优先使用我的标准
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={fallbackToDefault}
              onChange={(e) => setFallbackToDefault(e.target.checked)}
            />
            解析失败时回退系统默认
          </label>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={previewPolicy} disabled={loading || !policyText.trim()}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            解析预览
          </Button>
          <Button onClick={savePolicy} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            保存标准
          </Button>
        </div>
      </div>

      {policyWarnings.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          {policyWarnings.map((w, i) => (
            <p key={i}>- {w}</p>
          ))}
        </div>
      )}

      {policyPreview && (
        <div className="rounded-lg border p-4 space-y-3">
          <h3 className="font-medium">解析结果预览</h3>
          <p className="text-sm text-muted-foreground">风险偏好：{policyPreview.risk_tolerance || "balanced"}</p>
          <div>
            <p className="text-sm font-medium mb-1">必审项</p>
            <ul className="text-sm text-muted-foreground space-y-1">
              {(policyPreview.must_review_items || []).slice(0, 10).map((item: string, idx: number) => (
                <li key={idx}>- {item}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-sm font-medium mb-1">禁用项</p>
            <ul className="text-sm text-muted-foreground space-y-1">
              {(policyPreview.forbidden_terms || []).length === 0 ? (
                <li>- 无</li>
              ) : (
                (policyPreview.forbidden_terms || []).slice(0, 10).map((item: string, idx: number) => (
                  <li key={idx}>- {item}</li>
                ))
              )}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
