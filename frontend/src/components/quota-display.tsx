"use client";

import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface QuotaDisplayProps {
  label: string;
  used: number;
  total: number;
  unit?: string;
  showPercentage?: boolean;
  className?: string;
}

export function QuotaDisplay({
  label,
  used,
  total,
  unit = "",
  showPercentage = true,
  className,
}: QuotaDisplayProps) {
  const percentage = total > 0 ? Math.round((used / total) * 100) : 0;
  const remaining = total - used;
  
  let statusColor = "text-green-500";
  let progressColor = "";
  
  if (percentage >= 90) {
    statusColor = "text-red-500";
    progressColor = "[&>div]:bg-red-500";
  } else if (percentage >= 70) {
    statusColor = "text-yellow-500";
    progressColor = "[&>div]:bg-yellow-500";
  }
  
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className={statusColor}>
          {remaining} {unit} 剩余
          {showPercentage && ` (${100 - percentage}%)`}
        </span>
      </div>
      <Progress value={percentage} className={cn("h-2", progressColor)} />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>已用 {used} {unit}</span>
        <span>共 {total} {unit}</span>
      </div>
    </div>
  );
}

interface UsageSummaryProps {
  reviews: { used: number; total: number };
  comparisons: { used: number; total: number };
  messages: { used: number; total: number };
}

export function UsageSummary({ reviews, comparisons, messages }: UsageSummaryProps) {
  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      <h3 className="font-medium">使用情况</h3>
      
      <QuotaDisplay
        label="本月审核次数"
        used={reviews.used}
        total={reviews.total}
        unit="次"
      />
      
      <QuotaDisplay
        label="本月对比次数"
        used={comparisons.used}
        total={comparisons.total}
        unit="次"
      />
      
      <QuotaDisplay
        label="今日助理消息"
        used={messages.used}
        total={messages.total}
        unit="条"
      />
    </div>
  );
}
