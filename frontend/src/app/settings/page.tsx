"use client";

import { useState, useEffect } from "react";
import { User, Bell, Loader2, CheckCircle, Trash2, Download } from "lucide-react";
import { toastError, toastSuccess } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";
import { withVisitorHeaders } from "@/lib/api";
import { cn } from "@/lib/utils";

const tabs = [
  { id: "profile", label: "个人信息", icon: User },
  { id: "notifications", label: "通知设置", icon: Bell },
  { id: "account", label: "账号管理", icon: Trash2 },
];

export default function SettingsPage() {
  const { user, token, login } = useAuthStore();
  const [activeTab, setActiveTab] = useState("profile");

  // Profile state
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  // Notification state
  const [notifReview, setNotifReview] = useState(true);
  const [notifCompare, setNotifCompare] = useState(true);
  const [notifUpdates, setNotifUpdates] = useState(false);
  const [notifSaved, setNotifSaved] = useState(false);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
    }
  }, [user]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const param = new URLSearchParams(window.location.search).get("tab");
      if (param && tabs.some((t) => t.id === param)) {
        setActiveTab(param);
      }
    }
  }, []);

  const saveProfile = async () => {
    if (!token) return;
    setProfileSaving(true);
    setProfileSaved(false);
    try {
      const response = await fetch(`/api/auth/me?full_name=${encodeURIComponent(fullName)}`, {
        method: "PUT",
        headers: withVisitorHeaders({
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        }),
      });
      if (response.ok) {
        const updatedUser = await response.json();
        login(updatedUser, token);
        setProfileSaved(true);
        setTimeout(() => setProfileSaved(false), 3000);
      }
    } catch (error) {
      console.error("Failed to update profile:", error);
      toastError("保存失败，请重试");
    } finally {
      setProfileSaving(false);
    }
  };

  const saveNotifications = () => {
    // Notifications are client-side only for now
    localStorage.setItem(
      "notification_prefs",
      JSON.stringify({ review: notifReview, compare: notifCompare, updates: notifUpdates })
    );
    setNotifSaved(true);
    setTimeout(() => setNotifSaved(false), 3000);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">设置</h1>
        <p className="text-muted-foreground">管理您的账号和偏好设置</p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-48 shrink-0">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                  activeTab === tab.id
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent"
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 rounded-lg border bg-card p-6">
          {activeTab === "profile" && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold">个人信息</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">邮箱</label>
                  <input
                    type="email"
                    value={user?.email || ""}
                    disabled
                    className="mt-1 w-full rounded-lg border bg-muted px-4 py-2 text-muted-foreground"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    邮箱不可修改
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium">姓名</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="mt-1 w-full rounded-lg border bg-background px-4 py-2"
                    placeholder="请输入您的姓名"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <Button onClick={saveProfile} disabled={profileSaving}>
                    {profileSaving ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        保存中...
                      </>
                    ) : (
                      "保存修改"
                    )}
                  </Button>
                  {profileSaved && (
                    <span className="flex items-center gap-1 text-sm text-green-500">
                      <CheckCircle className="h-4 w-4" /> 已保存
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === "notifications" && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold">通知设置</h2>
              <div className="space-y-4">
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={notifReview}
                    onChange={(e) => setNotifReview(e.target.checked)}
                    className="h-4 w-4"
                  />
                  <span className="text-sm">审核完成通知</span>
                </label>
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={notifCompare}
                    onChange={(e) => setNotifCompare(e.target.checked)}
                    className="h-4 w-4"
                  />
                  <span className="text-sm">对比完成通知</span>
                </label>
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={notifUpdates}
                    onChange={(e) => setNotifUpdates(e.target.checked)}
                    className="h-4 w-4"
                  />
                  <span className="text-sm">产品更新通知</span>
                </label>
                <div className="flex items-center gap-3">
                  <Button onClick={saveNotifications}>保存设置</Button>
                  {notifSaved && (
                    <span className="flex items-center gap-1 text-sm text-green-500">
                      <CheckCircle className="h-4 w-4" /> 已保存
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === "account" && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold">账号管理</h2>

              {/* Data Export */}
              <div className="rounded-lg border p-4 space-y-2">
                <h3 className="font-medium">导出我的数据</h3>
                <p className="text-sm text-muted-foreground">
                  下载您在平台上的所有数据副本（符合《个人信息保护法》要求）
                </p>
                <Button
                  variant="outline"
                  onClick={async () => {
                    if (!token) return;
                    try {
                      const resp = await fetch("/api/auth/me/export", {
                        headers: withVisitorHeaders({ Authorization: `Bearer ${token}` }),
                      });
                      if (resp.ok) {
                        const data = await resp.json();
                        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = "my_data_export.json";
                        a.click();
                        URL.revokeObjectURL(url);
                        toastSuccess("数据导出成功");
                      }
                    } catch {
                      toastError("导出失败");
                    }
                  }}
                >
                  <Download className="mr-2 h-4 w-4" />
                  导出数据
                </Button>
              </div>

              {/* Account Deletion */}
              <div className="rounded-lg border border-destructive/50 p-4 space-y-2">
                <h3 className="font-medium text-destructive">注销账号</h3>
                <p className="text-sm text-muted-foreground">
                  注销后您的账号将被禁用，数据将在保留期后被永久删除。此操作不可撤销。
                </p>
                <Button
                  variant="destructive"
                  onClick={async () => {
                    if (!confirm("确定要注销账号吗？此操作不可撤销。")) return;
                    if (!token) return;
                    try {
                      const resp = await fetch("/api/auth/me", {
                        method: "DELETE",
                        headers: withVisitorHeaders({ Authorization: `Bearer ${token}` }),
                      });
                      if (resp.ok) {
                        const { logout: doLogout } = useAuthStore.getState();
                        doLogout();
                        window.location.href = "/";
                      }
                    } catch {
                      toastError("注销失败");
                    }
                  }}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  注销我的账号
                </Button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
