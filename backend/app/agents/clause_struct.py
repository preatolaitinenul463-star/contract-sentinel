"""Clause structuring agent - extracts structured clauses from contracts."""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from loguru import logger


@dataclass
class ExtractedClause:
    """A structured clause extracted from contract."""
    clause_type: str  # e.g., "payment", "delivery", "liability"
    title: Optional[str]
    content: str
    key_values: Dict[str, Any] = field(default_factory=dict)
    location: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContractStructure:
    """Structured representation of a contract."""
    parties: List[Dict[str, str]] = field(default_factory=list)
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    contract_amount: Optional[str] = None
    clauses: List[ExtractedClause] = field(default_factory=list)
    raw_text: str = ""


class ClauseStructAgent:
    """Agent for extracting structured clauses from contract text."""
    
    # Common clause patterns (Chinese contracts)
    CLAUSE_PATTERNS = {
        "parties": [
            r"甲方[：:]\s*(.+?)(?:\n|乙方)",
            r"乙方[：:]\s*(.+?)(?:\n|$)",
            r"委托方[：:]\s*(.+?)(?:\n|受托方)",
            r"受托方[：:]\s*(.+?)(?:\n|$)",
        ],
        "payment": [
            r"(付款|支付|结算).{0,50}(条款|方式|期限)",
            r"(合同|服务|产品).{0,30}(价格|金额|费用)",
            r"(人民币|元|万元).{0,50}(支付|付款|结算)",
        ],
        "delivery": [
            r"(交付|验收|完成).{0,50}(期限|时间|日期)",
            r"(工期|工程期限).{0,30}",
        ],
        "liability": [
            r"(违约|赔偿|责任).{0,50}(条款|规定)",
            r"(损失|损害).{0,30}(赔偿|承担)",
            r"违约金.{0,50}",
        ],
        "termination": [
            r"(解除|终止|中止).{0,50}(合同|协议)",
            r"(提前终止|单方解除).{0,30}",
        ],
        "confidentiality": [
            r"(保密|机密|商业秘密).{0,50}(条款|义务|规定)",
            r"(泄露|披露).{0,30}(禁止|不得)",
        ],
        "intellectual_property": [
            r"(知识产权|著作权|专利|商标).{0,50}(归属|所有|许可)",
        ],
        "dispute_resolution": [
            r"(争议|纠纷).{0,50}(解决|处理|管辖)",
            r"(仲裁|诉讼|法院).{0,30}",
        ],
        "force_majeure": [
            r"不可抗力.{0,50}",
        ],
    }
    
    async def extract_structure(self, text: str) -> ContractStructure:
        """Extract structured information from contract text."""
        structure = ContractStructure(raw_text=text)
        
        # Extract parties
        structure.parties = self._extract_parties(text)
        
        # Extract dates
        structure.effective_date = self._extract_date(text, "effective")
        structure.expiry_date = self._extract_date(text, "expiry")
        
        # Extract amount
        structure.contract_amount = self._extract_amount(text)
        
        # Extract clauses
        structure.clauses = self._extract_clauses(text)
        
        return structure
    
    def _extract_parties(self, text: str) -> List[Dict[str, str]]:
        """Extract contract parties."""
        parties = []
        
        # Look for common party patterns
        party_a_match = re.search(r"甲方[（(]?[：:]?\s*([^\n）)]+)", text)
        if party_a_match:
            parties.append({"role": "party_a", "name": party_a_match.group(1).strip()})
        
        party_b_match = re.search(r"乙方[（(]?[：:]?\s*([^\n）)]+)", text)
        if party_b_match:
            parties.append({"role": "party_b", "name": party_b_match.group(1).strip()})
        
        return parties
    
    def _extract_date(self, text: str, date_type: str) -> Optional[str]:
        """Extract dates from contract."""
        patterns = {
            "effective": [
                r"本合同自(\d{4}年\d{1,2}月\d{1,2}日)起生效",
                r"生效日期[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日)",
                r"签订日期[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日)",
            ],
            "expiry": [
                r"至(\d{4}年\d{1,2}月\d{1,2}日)止",
                r"有效期至(\d{4}年\d{1,2}月\d{1,2}日)",
                r"终止日期[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日)",
            ],
        }
        
        for pattern in patterns.get(date_type, []):
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_amount(self, text: str) -> Optional[str]:
        """Extract contract amount."""
        patterns = [
            r"合同[总金]?额[：:为]?\s*(人民币)?(\d[\d,，.]*)(万?元)",
            r"[总金]?[价款额][：:为]?\s*(人民币)?(\d[\d,，.]*)(万?元)",
            r"(人民币)(\d[\d,，.]*)(万?元)整?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                currency = groups[0] or "人民币"
                amount = groups[1].replace(",", "").replace("，", "")
                unit = groups[2]
                return f"{currency}{amount}{unit}"
        
        return None
    
    def _extract_clauses(self, text: str) -> List[ExtractedClause]:
        """Extract and classify clauses."""
        clauses = []
        
        # Split text into sections (by article numbers)
        article_pattern = r"(?:第[一二三四五六七八九十百]+条|[一二三四五六七八九十]+[、.]|\d+[、.])"
        sections = re.split(f"({article_pattern})", text)
        
        current_pos = 0
        for i in range(0, len(sections) - 1, 2):
            if i + 1 < len(sections):
                title = sections[i].strip() if i > 0 else ""
                content = sections[i + 1].strip() if i + 1 < len(sections) else ""
                
                if not content:
                    continue
                
                # Classify the clause
                clause_type = self._classify_clause(title + " " + content)
                
                clause = ExtractedClause(
                    clause_type=clause_type,
                    title=title,
                    content=content[:500],  # Limit length
                    location={"start": current_pos, "end": current_pos + len(content)},
                )
                clauses.append(clause)
                current_pos += len(content)
        
        return clauses
    
    def _classify_clause(self, text: str) -> str:
        """Classify a clause based on its content."""
        text_lower = text.lower()
        
        # Check each clause type's patterns
        for clause_type, patterns in self.CLAUSE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return clause_type
        
        return "other"
