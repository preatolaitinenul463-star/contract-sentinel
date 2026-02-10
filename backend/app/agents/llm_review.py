"""LLM Review Agent - Deep AI-powered contract analysis."""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json

from loguru import logger

from app.providers import get_provider_registry, ChatMessage


@dataclass
class LLMRiskItem:
    """Risk item identified by LLM."""
    severity: str  # high, medium, low
    name: str
    description: str
    clause_text: str
    suggestion: str
    legal_basis: Optional[str] = None  # 法律依据
    confidence: float = 0.8


@dataclass 
class LLMReviewResult:
    """Result from LLM review agent."""
    risk_items: List[LLMRiskItem]
    summary: str
    overall_risk_level: str  # high, medium, low
    model_used: str
    tokens_input: int
    tokens_output: int


class LLMReviewAgent:
    """
    LLM Review Agent - 深度 AI 审核
    
    职责：
    1. 分析条款的法律风险
    2. 识别不公平/霸王条款
    3. 检查合规性问题
    4. 提供专业法律分析
    """
    
    # 不同合同类型的审核重点
    REVIEW_FOCUS = {
        "general": ["权利义务对等", "违约责任", "争议解决", "免责条款"],
        "labor": ["工资福利", "工作时间", "竞业限制", "解除条件", "保密义务"],
        "tech": ["知识产权归属", "数据安全", "服务级别", "责任限制", "保密条款"],
        "sales": ["标的物风险", "付款条件", "质量保证", "退换货", "违约金"],
        "lease": ["租金调整", "押金退还", "维修责任", "提前解约", "续租条款"],
    }
    
    # 不同司法管辖区的法律要点
    JURISDICTION_FOCUS = {
        "CN": {
            "name": "中国大陆",
            "key_laws": ["民法典", "劳动合同法", "消费者权益保护法", "数据安全法"],
            "focus": ["格式条款效力", "违约金上限", "管辖约定"],
        },
        "HK": {
            "name": "中国香港",
            "key_laws": ["合约法", "雇佣条例", "个人资料(私隐)条例"],
            "focus": ["普通法原则", "免责条款合理性"],
        },
        "SG": {
            "name": "新加坡",
            "key_laws": ["Contracts Act", "Employment Act", "PDPA"],
            "focus": ["公平交易", "数据保护"],
        },
        "US": {
            "name": "美国",
            "key_laws": ["UCC", "State Contract Laws", "CCPA/CPRA"],
            "focus": ["州法差异", "仲裁条款", "集体诉讼弃权"],
        },
        "UK": {
            "name": "英国",
            "key_laws": ["Contracts Act", "Consumer Rights Act", "UK GDPR"],
            "focus": ["不公平条款", "消费者保护"],
        },
    }
    
    def __init__(self):
        self.registry = get_provider_registry()
    
    async def review(
        self,
        contract_text: str,
        contract_type: str = "general",
        jurisdiction: str = "CN",
        clauses: Optional[Dict[str, Any]] = None,
        rule_findings: Optional[List[Dict]] = None,
        provider_id: str = "deepseek",
        model: str = "deepseek-chat",
    ) -> LLMReviewResult:
        """
        执行深度 LLM 审核
        
        Args:
            contract_text: 合同全文
            contract_type: 合同类型
            jurisdiction: 司法管辖区
            clauses: 已提取的条款结构（来自 ClauseStructAgent）
            rule_findings: 规则引擎已发现的问题（来自 RuleEngineAgent）
            provider_id: LLM provider
            model: 具体模型
        """
        chat_client = self.registry.get_chat_client(provider_id, model)
        
        # 构建专业的系统提示
        system_prompt = self._build_system_prompt(contract_type, jurisdiction)
        
        # 构建用户消息，包含已知信息
        user_message = self._build_user_message(
            contract_text, clauses, rule_findings
        )
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]
        
        response = await chat_client.chat(messages, temperature=0.2)
        
        # 解析响应
        risk_items, summary, overall_risk = self._parse_response(response.content)
        
        return LLMReviewResult(
            risk_items=risk_items,
            summary=summary,
            overall_risk_level=overall_risk,
            model_used=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
        )
    
    def _build_system_prompt(self, contract_type: str, jurisdiction: str) -> str:
        """构建专业的系统提示"""
        focus_points = self.REVIEW_FOCUS.get(contract_type, self.REVIEW_FOCUS["general"])
        jur_info = self.JURISDICTION_FOCUS.get(jurisdiction, self.JURISDICTION_FOCUS["CN"])
        
        return f"""你是一位资深法务专家，精通{jur_info['name']}法律法规，尤其擅长合同审核。

## 你的专业背景
- 熟悉的法律：{', '.join(jur_info['key_laws'])}
- 审核重点：{', '.join(jur_info['focus'])}

## 当前任务
审核一份{contract_type}类型的合同，识别其中的法律风险。

## 审核重点
{chr(10).join(f'- {p}' for p in focus_points)}

## 输出要求
请以JSON格式输出审核结果：
{{
  "risk_items": [
    {{
      "severity": "high/medium/low",
      "name": "风险名称（简短）",
      "description": "详细风险描述",
      "clause_text": "相关条款原文（精确引用）",
      "suggestion": "具体修改建议",
      "legal_basis": "法律依据（如适用）",
      "confidence": 0.0-1.0
    }}
  ],
  "summary": "整体风险评估（2-3句话）",
  "overall_risk_level": "high/medium/low"
}}

## 审核原则
1. 严格基于合同原文，精确引用
2. 区分对甲方/乙方的风险
3. 提供可操作的修改建议
4. 标注法律依据增强可信度
5. 对不确定的问题标注较低置信度"""
    
    def _build_user_message(
        self,
        contract_text: str,
        clauses: Optional[Dict[str, Any]],
        rule_findings: Optional[List[Dict]],
    ) -> str:
        """构建用户消息"""
        parts = []
        
        # 已提取的结构信息
        if clauses:
            parts.append("## 已提取的合同信息")
            if clauses.get("parties"):
                parts.append(f"- 签约方：{', '.join(clauses['parties'])}")
            if clauses.get("effective_date"):
                parts.append(f"- 生效日期：{clauses['effective_date']}")
            if clauses.get("contract_amount"):
                parts.append(f"- 合同金额：{clauses['contract_amount']}")
            parts.append("")
        
        # 规则引擎已发现的问题
        if rule_findings:
            parts.append("## 规则检查已发现的问题（请勿重复）")
            for finding in rule_findings[:5]:  # 最多显示5个
                parts.append(f"- {finding.get('name', '')}: {finding.get('description', '')}")
            parts.append("")
            parts.append("请重点发现规则检查未能覆盖的深层风险。")
            parts.append("")
        
        # 合同全文
        parts.append("## 合同全文")
        # 截断过长的合同
        max_length = 12000
        if len(contract_text) > max_length:
            parts.append(contract_text[:max_length])
            parts.append(f"\n... (合同过长，已截取前{max_length}字)")
        else:
            parts.append(contract_text)
        
        return "\n".join(parts)
    
    def _parse_response(self, content: str) -> tuple:
        """解析 LLM 响应"""
        try:
            # 提取 JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content
            
            data = json.loads(json_str)
            
            risk_items = []
            for item in data.get("risk_items", []):
                risk_items.append(LLMRiskItem(
                    severity=item.get("severity", "medium"),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    clause_text=item.get("clause_text", ""),
                    suggestion=item.get("suggestion", ""),
                    legal_basis=item.get("legal_basis"),
                    confidence=item.get("confidence", 0.8),
                ))
            
            summary = data.get("summary", "审核完成")
            overall_risk = data.get("overall_risk_level", "medium")
            
            return risk_items, summary, overall_risk
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return [], content[:500], "medium"
