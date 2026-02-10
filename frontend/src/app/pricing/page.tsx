"use client";

import { useState } from "react";
import { Check, Zap, Building2, Crown, Mail, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const plans = [
  {
    id: "free",
    name: "免费版",
    price: 0,
    priceUnit: "永久免费",
    description: "适合个人用户体验",
    icon: Zap,
    features: [
      "每月10次合同审核",
      "每月5次合同对比",
      "每日20条助理消息",
      "最大10MB文件",
      "基础风险检测",
    ],
    notIncluded: [
      "法规检索功能",
      "报告导出",
      "优先支持",
    ],
    buttonText: "当前套餐",
    buttonVariant: "outline" as const,
    popular: false,
  },
  {
    id: "basic",
    name: "基础版",
    price: 99,
    priceUnit: "元/月",
    description: "适合小型团队日常使用",
    icon: Check,
    features: [
      "每月50次合同审核",
      "每月20次合同对比",
      "每日100条助理消息",
      "最大30MB文件",
      "完整风险检测",
      "法规检索功能",
      "报告导出(Word/PDF)",
    ],
    notIncluded: [
      "优先技术支持",
    ],
    buttonText: "升级套餐",
    buttonVariant: "default" as const,
    popular: false,
  },
  {
    id: "pro",
    name: "专业版",
    price: 299,
    priceUnit: "元/月",
    description: "适合专业法务团队",
    icon: Crown,
    features: [
      "每月200次合同审核",
      "每月100次合同对比",
      "每日500条助理消息",
      "最大50MB文件",
      "深度风险分析",
      "法规检索功能",
      "报告导出(Word/PDF)",
      "优先技术支持",
    ],
    notIncluded: [],
    buttonText: "升级套餐",
    buttonVariant: "default" as const,
    popular: true,
  },
  {
    id: "enterprise",
    name: "企业版",
    price: null,
    priceUnit: "联系销售",
    description: "适合大型企业定制需求",
    icon: Building2,
    features: [
      "无限次合同审核",
      "无限次合同对比",
      "无限助理消息",
      "最大100MB文件",
      "定制规则包",
      "API集成",
      "私有化部署",
      "专属客户经理",
    ],
    notIncluded: [],
    buttonText: "联系我们",
    buttonVariant: "outline" as const,
    popular: false,
  },
];

export default function PricingPage() {
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
  const [showContactModal, setShowContactModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState("");
  const { user } = useAuthStore();

  const handleUpgrade = (planId: string) => {
    if (planId === "free") return;
    setSelectedPlan(planId);
    setShowContactModal(true);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold">选择适合您的套餐</h1>
        <p className="mt-2 text-muted-foreground">
          灵活的定价方案，满足不同规模团队的需求
        </p>
      </div>

      {/* Billing Toggle */}
      <div className="flex justify-center">
        <div className="inline-flex rounded-lg border p-1">
          <button
            onClick={() => setBillingCycle("monthly")}
            className={cn(
              "rounded-md px-4 py-2 text-sm font-medium transition-colors",
              billingCycle === "monthly"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            月付
          </button>
          <button
            onClick={() => setBillingCycle("yearly")}
            className={cn(
              "rounded-md px-4 py-2 text-sm font-medium transition-colors",
              billingCycle === "yearly"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            年付 <span className="text-xs text-green-500">省20%</span>
          </button>
        </div>
      </div>

      {/* Plans Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => {
          const Icon = plan.icon;
          const displayPrice = plan.price !== null
            ? billingCycle === "yearly"
              ? Math.round(plan.price * 12 * 0.8)
              : plan.price
            : null;
          
          return (
            <div
              key={plan.id}
              className={cn(
                "relative rounded-lg border bg-card p-6 transition-shadow hover:shadow-md",
                plan.popular && "border-primary ring-1 ring-primary"
              )}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
                    最受欢迎
                  </span>
                </div>
              )}
              
              <div className="mb-4">
                <Icon className="h-8 w-8 text-primary" />
              </div>
              
              <h3 className="text-xl font-semibold">{plan.name}</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {plan.description}
              </p>
              
              <div className="my-4">
                {displayPrice !== null ? (
                  <>
                    <span className="text-3xl font-bold">¥{displayPrice}</span>
                    <span className="text-muted-foreground">
                      /{billingCycle === "yearly" ? "年" : "月"}
                    </span>
                  </>
                ) : (
                  <span className="text-xl font-semibold">{plan.priceUnit}</span>
                )}
              </div>
              
              <Button
                variant={plan.buttonVariant}
                className="w-full"
                disabled={plan.id === "free" || (user?.plan_type === plan.id)}
                onClick={() => handleUpgrade(plan.id)}
              >
                {user?.plan_type === plan.id ? "当前套餐" : plan.buttonText}
              </Button>
              
              <ul className="mt-6 space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <Check className="h-4 w-4 shrink-0 text-green-500 mt-0.5" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
                {plan.notIncluded.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-muted-foreground">
                    <span className="h-4 w-4 shrink-0 text-center mt-0.5">-</span>
                    <span className="text-sm line-through">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {/* FAQ Section */}
      <div className="rounded-lg border bg-card p-8">
        <h2 className="text-xl font-semibold">常见问题</h2>
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="font-medium">可以随时升级或降级吗？</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              是的，您可以随时升级套餐，差价将按比例计算。降级将在当前计费周期结束后生效。
            </p>
          </div>
          <div>
            <h3 className="font-medium">支持哪些付款方式？</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              我们支持支付宝、微信支付、银行卡以及企业对公转账。
            </p>
          </div>
          <div>
            <h3 className="font-medium">如何申请发票？</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              付款完成后，您可以在设置中申请电子发票，我们将在3个工作日内开具。
            </p>
          </div>
          <div>
            <h3 className="font-medium">企业版有什么特别之处？</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              企业版支持私有化部署、定制规则包、API集成等高级功能，并配有专属客户经理。
            </p>
          </div>
        </div>
      </div>

      {/* Contact */}
      <div className="text-center">
        <p className="text-muted-foreground">
          有更多问题？
          <a href="mailto:support@contract-sentinel.ai" className="text-primary hover:underline ml-1">
            联系我们
          </a>
        </p>
      </div>

      {/* Contact / Upgrade Modal */}
      {showContactModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="relative w-full max-w-md rounded-lg border bg-card p-6 shadow-lg mx-4">
            <button
              onClick={() => setShowContactModal(false)}
              className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="text-center space-y-4">
              <Mail className="h-12 w-12 text-primary mx-auto" />
              <h3 className="text-xl font-semibold">
                升级到{selectedPlan === "basic" ? "基础版" : selectedPlan === "pro" ? "专业版" : "企业版"}
              </h3>
              <p className="text-sm text-muted-foreground">
                付费功能即将上线。请通过以下方式联系我们，我们将为您优先开通。
              </p>
              <div className="rounded-lg bg-muted p-4 text-left space-y-2">
                <p className="text-sm">
                  <span className="font-medium">邮箱：</span>
                  <a href="mailto:support@contract-sentinel.ai" className="text-primary">
                    support@contract-sentinel.ai
                  </a>
                </p>
                <p className="text-sm">
                  <span className="font-medium">备注：</span>
                  请注明您的注册邮箱和希望升级的套餐
                </p>
              </div>
              <Button
                className="w-full"
                onClick={() => {
                  window.location.href = `mailto:support@contract-sentinel.ai?subject=套餐升级申请 - ${selectedPlan}&body=您好，我希望升级到${selectedPlan}套餐。%0A%0A注册邮箱：${user?.email || ""}%0A`;
                }}
              >
                <Mail className="mr-2 h-4 w-4" />
                发送邮件
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
