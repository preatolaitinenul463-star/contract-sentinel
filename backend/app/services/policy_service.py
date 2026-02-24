"""Policy service for user standards and default fallbacks."""
from __future__ import annotations

import re
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import UserPolicy

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "rules" / "default_policy_cn.json"
DEFAULT_POLICY_VERSION = "default-v1"


def _load_default_must_review() -> Dict[str, List[str]]:
    try:
        with open(DEFAULT_POLICY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            version = data.get("version")
            must = data.get("must_review")
            if isinstance(must, dict):
                if isinstance(version, str):
                    global DEFAULT_POLICY_VERSION
                    DEFAULT_POLICY_VERSION = version
                return {k: [str(x) for x in v] for k, v in must.items() if isinstance(v, list)}
    except Exception:
        pass
    return {
        "general": ["合同主体与授权资格是否明确", "标的/服务范围是否明确", "争议解决地是否明显不利"],
        "labor": ["试用期合法性与工资比例"],
        "tech": ["数据出境与安全责任是否明确"],
        "sales": ["质量标准与检验流程"],
        "lease": ["押金退还条件"],
    }


DEFAULT_MUST_REVIEW: Dict[str, List[str]] = _load_default_must_review()


@dataclass
class ResolvedPolicy:
    source: str  # user | default
    policy_version: str
    prefer_user_standard: bool
    fallback_to_default: bool
    contract_type: str
    jurisdiction: str
    must_review_items: List[str]
    forbidden_terms: List[str]
    risk_tolerance: str  # conservative | balanced | aggressive
    output_constraints: Dict[str, Any]
    parse_warnings: List[str]

    def as_prompt_block(self) -> str:
        must = "\n".join(f"- {x}" for x in self.must_review_items)
        forbid = "\n".join(f"- {x}" for x in self.forbidden_terms) if self.forbidden_terms else "- 无"
        return (
            f"## 企业/个人审核规格（必须执行）\n"
            f"- 策略来源: {self.source}\n"
            f"- 策略版本: {self.policy_version}\n"
            f"- 合同类型: {self.contract_type}\n"
            f"- 法域: {self.jurisdiction}\n"
            f"- 风险偏好: {self.risk_tolerance}\n"
            f"### 必审项\n{must}\n"
            f"### 禁用项\n{forbid}\n"
            f"### 输出约束\n"
            f"- 每条风险必须包含：风险位置、风险描述、法律依据、修改建议\n"
            f"- 无依据结论必须明确标注“不确定”\n"
        )


class PolicyService:
    """Resolve per-user policy with safe default fallback."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_default(self, user_id: Optional[int], contract_type: str, jurisdiction: str) -> ResolvedPolicy:
        if user_id:
            result = await self.db.execute(select(UserPolicy).where(UserPolicy.user_id == user_id))
            row = result.scalar_one_or_none()
            if row:
                resolved = self._from_user_policy(row, contract_type=contract_type, jurisdiction=jurisdiction)
                if resolved.source == "user" or not resolved.fallback_to_default:
                    return resolved
        return self.default_policy(contract_type=contract_type, jurisdiction=jurisdiction)

    async def upsert_user_policy(
        self,
        user_id: int,
        standard_text: str,
        prefer_user_standard: bool = True,
        fallback_to_default: bool = True,
    ) -> UserPolicy:
        parsed, warnings = self.parse_standard_text(standard_text)
        result = await self.db.execute(select(UserPolicy).where(UserPolicy.user_id == user_id))
        row = result.scalar_one_or_none()
        if row:
            row.standard_text = standard_text
            row.parsed_policy = {**parsed, "parse_warnings": warnings}
            row.prefer_user_standard = prefer_user_standard
            row.fallback_to_default = fallback_to_default
            row.version += 1
        else:
            row = UserPolicy(
                user_id=user_id,
                standard_text=standard_text,
                parsed_policy={**parsed, "parse_warnings": warnings},
                prefer_user_standard=prefer_user_standard,
                fallback_to_default=fallback_to_default,
                version=1,
            )
            self.db.add(row)
        await self.db.flush()
        return row

    def parse_standard_text(self, text: str) -> tuple[Dict[str, Any], List[str]]:
        """Lightweight parser for user standards with safe defaults."""
        warnings: List[str] = []
        if not text or len(text.strip()) < 20:
            warnings.append("标准文本过短，已回退默认策略")
            return {"must_review_items": [], "forbidden_terms": [], "risk_tolerance": "balanced"}, warnings

        norm = re.sub(r"\r\n?", "\n", text)
        lines = [ln.strip("-* \t") for ln in norm.split("\n") if ln.strip()]

        must_items: List[str] = []
        forbidden: List[str] = []
        risk_tolerance = "balanced"

        for ln in lines:
            if any(k in ln for k in ("必须", "必审", "重点关注", "应当")):
                must_items.append(ln[:120])
            if any(k in ln for k in ("禁止", "不得", "不接受", "不可")):
                forbidden.append(ln[:120])
            if "保守" in ln or "严格" in ln or "高标准" in ln:
                risk_tolerance = "conservative"
            if "激进" in ln or "宽松" in ln:
                risk_tolerance = "aggressive"

        if not must_items:
            warnings.append("未识别到“必审项”，将叠加系统默认必审清单")
        if len(must_items) > 20:
            warnings.append("必审项较多，建议精简到20条以内以提升稳定性")

        return {
            "must_review_items": must_items[:20],
            "forbidden_terms": forbidden[:20],
            "risk_tolerance": risk_tolerance,
        }, warnings

    def default_policy(self, contract_type: str, jurisdiction: str) -> ResolvedPolicy:
        type_key = contract_type if contract_type in DEFAULT_MUST_REVIEW else "general"
        must = list(DEFAULT_MUST_REVIEW["general"])
        if type_key != "general":
            must.extend(DEFAULT_MUST_REVIEW.get(type_key, []))
        return ResolvedPolicy(
            source="default",
            policy_version=DEFAULT_POLICY_VERSION,
            prefer_user_standard=True,
            fallback_to_default=True,
            contract_type=type_key,
            jurisdiction=jurisdiction,
            must_review_items=must,
            forbidden_terms=[],
            risk_tolerance="balanced",
            output_constraints={"schema_required": True, "require_legal_basis": True},
            parse_warnings=[],
        )

    def _from_user_policy(self, row: UserPolicy, contract_type: str, jurisdiction: str) -> ResolvedPolicy:
        parsed = row.parsed_policy or {}
        warnings = parsed.get("parse_warnings", [])
        must_items = parsed.get("must_review_items") or []
        forbidden = parsed.get("forbidden_terms") or []
        risk_tolerance = parsed.get("risk_tolerance", "balanced")

        if not row.prefer_user_standard:
            return self.default_policy(contract_type=contract_type, jurisdiction=jurisdiction)

        if not must_items and row.fallback_to_default:
            default = self.default_policy(contract_type=contract_type, jurisdiction=jurisdiction)
            default.parse_warnings = warnings
            return default

        default_items = self.default_policy(contract_type=contract_type, jurisdiction=jurisdiction).must_review_items
        merged_items = must_items + [x for x in default_items if x not in must_items]

        return ResolvedPolicy(
            source="user",
            policy_version=f"user-{row.user_id}-v{row.version}",
            prefer_user_standard=row.prefer_user_standard,
            fallback_to_default=row.fallback_to_default,
            contract_type=contract_type,
            jurisdiction=jurisdiction,
            must_review_items=merged_items,
            forbidden_terms=forbidden,
            risk_tolerance=risk_tolerance,
            output_constraints={"schema_required": True, "require_legal_basis": True},
            parse_warnings=warnings,
        )


def suggest_contract_type(text: str) -> Dict[str, Any]:
    """Lightweight contract type suggestion to reduce user interactions."""
    text_l = (text or "").lower()
    rules = [
        ("labor", ["劳动", "试用期", "竞业限制", "五险一金", "解除劳动"]),
        ("tech", ["软件", "系统", "源代码", "接口", "技术服务", "sla"]),
        ("sales", ["买方", "卖方", "货物", "交货", "质保", "采购", "订单"]),
        ("lease", ["租赁", "租金", "押金", "出租", "承租"]),
    ]
    for ctype, kws in rules:
        hit = sum(1 for k in kws if k in text_l)
        if hit >= 2:
            return {"suggested_contract_type": ctype, "confidence": min(0.95, 0.55 + 0.1 * hit)}
    return {"suggested_contract_type": "general", "confidence": 0.5}
