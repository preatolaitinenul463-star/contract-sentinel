"use client";

import { useState } from "react";
import { Users, Mail, UserPlus, Shield, Crown, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";
import { toastSuccess, toastError } from "@/lib/toast";

interface TeamMember {
  id: number;
  email: string;
  name: string;
  role: "owner" | "admin" | "member";
  joined_at: string;
}

export default function TeamPage() {
  const { user, isAuthenticated } = useAuthStore();
  const [inviteEmail, setInviteEmail] = useState("");
  const [members] = useState<TeamMember[]>([
    {
      id: 1,
      email: user?.email || "you@example.com",
      name: user?.full_name || "我",
      role: "owner",
      joined_at: new Date().toISOString(),
    },
  ]);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    // Placeholder - backend team endpoints not yet implemented
    toastSuccess(`已发送邀请到 ${inviteEmail}`);
    setInviteEmail("");
  };

  const roleLabels: Record<string, { label: string; icon: any }> = {
    owner: { label: "所有者", icon: Crown },
    admin: { label: "管理员", icon: Shield },
    member: { label: "成员", icon: Users },
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">团队管理</h1>
        <p className="text-muted-foreground">
          邀请团队成员共享审核结果和合同库
        </p>
      </div>

      {/* Invite */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">邀请成员</h2>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="输入邮箱地址"
              className="w-full rounded-lg border bg-background pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              onKeyDown={(e) => e.key === "Enter" && handleInvite()}
            />
          </div>
          <Button onClick={handleInvite} disabled={!inviteEmail.trim()}>
            <UserPlus className="mr-2 h-4 w-4" />
            邀请
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          受邀成员将收到邮件通知，接受邀请后可访问团队共享的合同和审核结果
        </p>
      </div>

      {/* Members list */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">团队成员</h2>
        <div className="space-y-3">
          {members.map((member) => {
            const roleInfo = roleLabels[member.role];
            const RoleIcon = roleInfo.icon;
            return (
              <div
                key={member.id}
                className="flex items-center gap-3 rounded-lg border p-3"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Users className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">{member.name}</p>
                  <p className="text-xs text-muted-foreground">{member.email}</p>
                </div>
                <span className="flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                  <RoleIcon className="h-3 w-3" />
                  {roleInfo.label}
                </span>
                {member.role !== "owner" && (
                  <button className="text-muted-foreground hover:text-red-500">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Plan note */}
      <div className="rounded-lg bg-muted p-4 text-center text-sm text-muted-foreground">
        <p>团队协作功能需要基础版或更高套餐。</p>
        <a href="/pricing" className="text-primary hover:underline">
          查看套餐详情
        </a>
      </div>
    </div>
  );
}
