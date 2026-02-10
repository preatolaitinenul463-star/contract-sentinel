"""Rule engine agent - applies deterministic rules to identify risks."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml
from loguru import logger


@dataclass
class RuleMatch:
    """A matched rule result."""
    rule_id: str
    severity: str
    name: str
    description: str
    matched_text: str
    location: Dict[str, Any] = field(default_factory=dict)
    suggestion: Optional[str] = None


@dataclass
class Rule:
    """A single rule definition."""
    id: str
    severity: str
    name: str
    description: str
    pattern_keywords: List[str] = field(default_factory=list)
    check_type: str = "keyword"  # keyword, regex, llm_assisted
    rule_logic: Optional[str] = None
    suggestion: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rule":
        return cls(
            id=data.get("id", ""),
            severity=data.get("severity", "medium"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            pattern_keywords=data.get("pattern_keywords", []),
            check_type=data.get("check_type", "keyword"),
            rule_logic=data.get("rule_logic"),
            suggestion=data.get("suggestion"),
        )


@dataclass
class RulePack:
    """A collection of rules for a jurisdiction/contract type."""
    jurisdiction: str
    contract_type: str
    rules: List[Rule] = field(default_factory=list)


class RuleEngineAgent:
    """Agent for applying deterministic rules to contracts."""
    
    def __init__(self):
        self.rule_packs: Dict[str, RulePack] = {}
        self._load_rule_packs()
    
    def _load_rule_packs(self) -> None:
        """Load rule packs from rules directory."""
        rules_dir = Path(__file__).parent.parent / "rules"
        
        if not rules_dir.exists():
            logger.warning(f"Rules directory not found: {rules_dir}")
            return
        
        for yaml_file in rules_dir.glob("*.yaml"):
            if yaml_file.name.startswith("_"):
                continue  # Skip schema files
            
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                if data:
                    pack = RulePack(
                        jurisdiction=data.get("jurisdiction", ""),
                        contract_type=data.get("contract_type", ""),
                        rules=[Rule.from_dict(r) for r in data.get("rules", [])],
                    )
                    pack_id = f"{pack.jurisdiction}_{pack.contract_type}"
                    self.rule_packs[pack_id] = pack
                    logger.info(f"Loaded rule pack: {pack_id} ({len(pack.rules)} rules)")
            except Exception as e:
                logger.error(f"Failed to load rule pack {yaml_file}: {e}")
    
    def check(
        self,
        text: str,
        jurisdiction: str = "CN",
        contract_type: str = "general",
    ) -> List[RuleMatch]:
        """Check text against rules and return matches."""
        matches = []
        
        # Get applicable rule packs
        pack_ids = [
            f"{jurisdiction}_{contract_type}",
            f"{jurisdiction}_general",
        ]
        
        for pack_id in pack_ids:
            pack = self.rule_packs.get(pack_id)
            if not pack:
                continue
            
            for rule in pack.rules:
                match_result = self._check_rule(text, rule)
                if match_result:
                    matches.append(match_result)
        
        return matches
    
    def _check_rule(self, text: str, rule: Rule) -> Optional[RuleMatch]:
        """Check a single rule against text."""
        if rule.check_type == "keyword":
            return self._check_keyword_rule(text, rule)
        elif rule.check_type == "regex":
            return self._check_regex_rule(text, rule)
        elif rule.check_type == "rule_match":
            return self._check_logic_rule(text, rule)
        else:
            # llm_assisted rules are handled separately
            return None
    
    def _check_keyword_rule(self, text: str, rule: Rule) -> Optional[RuleMatch]:
        """Check rule by keyword presence."""
        for keyword in rule.pattern_keywords:
            pattern = re.compile(f".{{0,100}}{re.escape(keyword)}.{{0,100}}", re.DOTALL)
            match = pattern.search(text)
            if match:
                return RuleMatch(
                    rule_id=rule.id,
                    severity=rule.severity,
                    name=rule.name,
                    description=rule.description,
                    matched_text=match.group(0).strip(),
                    suggestion=rule.suggestion,
                )
        return None
    
    def _check_regex_rule(self, text: str, rule: Rule) -> Optional[RuleMatch]:
        """Check rule by regex pattern."""
        for pattern_str in rule.pattern_keywords:
            try:
                pattern = re.compile(pattern_str, re.DOTALL)
                match = pattern.search(text)
                if match:
                    return RuleMatch(
                        rule_id=rule.id,
                        severity=rule.severity,
                        name=rule.name,
                        description=rule.description,
                        matched_text=match.group(0).strip(),
                        suggestion=rule.suggestion,
                    )
            except re.error:
                logger.warning(f"Invalid regex pattern in rule {rule.id}: {pattern_str}")
        return None
    
    def _check_logic_rule(self, text: str, rule: Rule) -> Optional[RuleMatch]:
        """Check rule by simple logic expression."""
        if not rule.rule_logic:
            return None
        
        logic = rule.rule_logic
        
        # Handle simple logic: NOT contains_any('a','b','c')
        if "NOT contains_any" in logic:
            match = re.search(r"contains_any\(([^)]+)\)", logic)
            if match:
                terms = [t.strip().strip("'\"") for t in match.group(1).split(",")]
                
                # First check if any keyword is present
                keyword_found = False
                matched_text = ""
                for keyword in rule.pattern_keywords:
                    pattern = re.compile(f".{{0,100}}{re.escape(keyword)}.{{0,100}}", re.DOTALL)
                    m = pattern.search(text)
                    if m:
                        keyword_found = True
                        matched_text = m.group(0).strip()
                        break
                
                if keyword_found:
                    # Check if any of the required terms are present
                    has_protection = any(term in text for term in terms)
                    if not has_protection:
                        return RuleMatch(
                            rule_id=rule.id,
                            severity=rule.severity,
                            name=rule.name,
                            description=rule.description,
                            matched_text=matched_text,
                            suggestion=rule.suggestion,
                        )
        
        return None
    
    def get_llm_assisted_rules(
        self,
        jurisdiction: str = "CN",
        contract_type: str = "general",
    ) -> List[Rule]:
        """Get rules that need LLM assistance."""
        rules = []
        
        pack_ids = [
            f"{jurisdiction}_{contract_type}",
            f"{jurisdiction}_general",
        ]
        
        for pack_id in pack_ids:
            pack = self.rule_packs.get(pack_id)
            if not pack:
                continue
            
            for rule in pack.rules:
                if rule.check_type == "llm_assisted":
                    rules.append(rule)
        
        return rules
