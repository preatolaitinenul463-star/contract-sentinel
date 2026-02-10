"""Redline Draft Agent - Generate contract modification suggestions."""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json

from loguru import logger

from app.providers import get_provider_registry, ChatMessage


@dataclass
class RedlineItem:
    """A single redline modification."""
    original_text: str
    modified_text: str
    change_type: str  # delete, insert, replace
    reason: str
    risk_id: Optional[str] = None  # 关联的风险项ID


@dataclass
class RedlineResult:
    """Result from redline drafting."""
    redlines: List[RedlineItem]
    modified_contract: str  # 完整修改后的合同文本
    change_summary: str
    model_used: str
    tokens_input: int
    tokens_output: int


class RedlineDraftAgent:
    """
    Redline Draft Agent - 修改建议生成
    
    职责：
    1. 根据风险项生成具体修改文本
    2. 保持合同整体结构和语言风格
    3. 确保修改后的条款法律上可行
    4. 生成可直接使用的修订版本
    """
    
    def __init__(self):
        self.registry = get_provider_registry()
    
    async def generate_redlines(
        self,
        contract_text: str,
        risk_items: List[Dict[str, Any]],
        contract_type: str = "general",
        jurisdiction: str = "CN",
        provider_id: str = "deepseek",
        model: str = "deepseek-chat",
    ) -> RedlineResult:
        """
        生成修改建议
        
        Args:
            contract_text: 合同原文
            risk_items: 需要处理的风险项
            contract_type: 合同类型
            jurisdiction: 司法管辖区
        """
        if not risk_items:
            return RedlineResult(
                redlines=[],
                modified_contract=contract_text,
                change_summary="无需修改",
                model_used="",
                tokens_input=0,
                tokens_output=0,
            )
        
        chat_client = self.registry.get_chat_client(provider_id, model)
        
        system_prompt = self._build_system_prompt(contract_type, jurisdiction)
        user_message = self._build_user_message(contract_text, risk_items)
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]
        
        response = await chat_client.chat(messages, temperature=0.3)
        
        redlines, modified_contract, summary = self._parse_response(
            response.content, contract_text
        )
        
        return RedlineResult(
            redlines=redlines,
            modified_contract=modified_contract,
            change_summary=summary,
            model_used=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
        )
    
    def _build_system_prompt(self, contract_type: str, jurisdiction: str) -> str:
        """构建系统提示"""
        return f"""你是一位专业的合同修订专家，负责根据风险分析结果生成合同修改建议。

## 任务
针对{contract_type}类型合同（适用{jurisdiction}法律），根据风险分析结果生成具体的条款修改建议。

## 修订原则
1. **最小改动原则**：只修改必要的部分，保持合同整体结构
2. **保护委托方**：修改方向应保护我方（审核委托方）利益
3. **法律可行性**：确保修改后的条款符合法律规定
4. **语言风格一致**：保持与原合同相同的语言风格和格式
5. **平衡双方利益**：避免过于偏激导致对方拒绝

## 输出格式（JSON）
{{
  "redlines": [
    {{
      "original_text": "原条款文本（精确引用）",
      "modified_text": "修改后的条款文本",
      "change_type": "replace/delete/insert",
      "reason": "修改理由",
      "risk_id": "关联的风险ID（如有）"
    }}
  ],
  "change_summary": "修改概述（简要说明主要修改）"
}}

## 注意事项
- 原文必须精确匹配合同中的实际文字
- 修改后的文本应完整、可直接使用
- 每个修改都要说明理由"""
    
    def _build_user_message(
        self,
        contract_text: str,
        risk_items: List[Dict[str, Any]],
    ) -> str:
        """构建用户消息"""
        parts = ["## 需要处理的风险项"]
        
        for i, item in enumerate(risk_items[:10], 1):  # 最多处理10个
            parts.append(f"""
### 风险 {i}: {item.get('name', '')}
- 风险等级：{item.get('severity', 'medium')}
- 描述：{item.get('description', '')}
- 相关条款：{item.get('clause_text', '')[:200]}
- 建议方向：{item.get('suggestion', '')}
""")
        
        parts.append("\n## 合同原文")
        # 截断过长合同
        max_length = 10000
        if len(contract_text) > max_length:
            parts.append(contract_text[:max_length])
            parts.append(f"\n... (已截取前{max_length}字)")
        else:
            parts.append(contract_text)
        
        return "\n".join(parts)
    
    def _parse_response(
        self, content: str, original_contract: str
    ) -> tuple:
        """解析响应"""
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content
            
            data = json.loads(json_str)
            
            redlines = []
            modified_contract = original_contract
            
            for item in data.get("redlines", []):
                original = item.get("original_text", "")
                modified = item.get("modified_text", "")
                
                redlines.append(RedlineItem(
                    original_text=original,
                    modified_text=modified,
                    change_type=item.get("change_type", "replace"),
                    reason=item.get("reason", ""),
                    risk_id=item.get("risk_id"),
                ))
                
                # 应用修改到合同文本
                if original and modified and original in modified_contract:
                    modified_contract = modified_contract.replace(
                        original, modified, 1
                    )
            
            summary = data.get("change_summary", "已生成修改建议")
            
            return redlines, modified_contract, summary
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse redline response: {e}")
            return [], original_contract, "解析修改建议失败"
