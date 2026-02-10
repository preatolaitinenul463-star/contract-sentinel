"""JurisdictionAgent (rule‑based) — maps jurisdiction codes to
search strategies, citation formats, and preferred legal sources.

This is the Cross‑Jurisdiction Bridge from the paper framework.
"""

from __future__ import annotations
from typing import Dict, List


# ── Citation format templates per jurisdiction ──

CITATION_FORMATS: Dict[str, str] = {
    "CN": "**《{law_name}》第{article}条**",
    "HK": "**{law_name}, s.{article}**",
    "SG": "**{law_name}, s {article}**",
    "UK": "**{law_name}, s.{article}**",
    "US": "**{law_name} § {article}**",
}

# ── Preferred search keywords per jurisdiction ──

JURISDICTION_KEYWORDS: Dict[str, str] = {
    "CN": "中华人民共和国 法律 法规",
    "HK": "香港法例 Hong Kong Ordinance",
    "SG": "Singapore Statutes",
    "UK": "UK Legislation Act",
    "US": "United States Code CFR",
}

# ── Disclaimer templates ──

DISCLAIMER_TEMPLATES: Dict[str, str] = {
    "CN": "本分析仅供参考，不构成法律意见。重要法律决策请咨询持证律师。",
    "HK": "本分析仅供参考。如涉及具体法律事务，请咨询香港执业律师。",
    "SG": "This analysis is for reference only. Please consult a qualified lawyer for specific legal matters.",
    "UK": "This analysis is for reference only. Please consult a qualified solicitor or barrister.",
    "US": "This analysis is for informational purposes only and does not constitute legal advice.",
}

# ── Compliance requirements per jurisdiction ──

COMPLIANCE_RULES: Dict[str, List[str]] = {
    "CN": [
        "必须使用中文法条全称",
        "引用法条时注明条款号",
        "涉及个人信息时注明《个人信息保护法》适用性",
    ],
    "HK": [
        "Citation must include Cap. number",
        "Distinguish between primary and subsidiary legislation",
    ],
    "SG": [
        "Reference Singapore Statutes Online (SSO) as authoritative source",
    ],
    "UK": [
        "Use official UK Legislation website as primary source",
    ],
    "US": [
        "Distinguish federal and state law applicability",
    ],
}


def get_citation_format(jurisdiction: str) -> str:
    return CITATION_FORMATS.get(jurisdiction, CITATION_FORMATS["CN"])


def get_search_keywords(jurisdiction: str) -> str:
    return JURISDICTION_KEYWORDS.get(jurisdiction, JURISDICTION_KEYWORDS["CN"])


def get_disclaimer(jurisdiction: str) -> str:
    return DISCLAIMER_TEMPLATES.get(jurisdiction, DISCLAIMER_TEMPLATES["CN"])


def get_compliance_rules(jurisdiction: str) -> List[str]:
    return COMPLIANCE_RULES.get(jurisdiction, COMPLIANCE_RULES["CN"])
