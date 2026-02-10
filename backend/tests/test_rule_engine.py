"""Tests for RuleEngineAgent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.rule_engine import RuleEngineAgent


class TestRuleEngine:
    """Test rule engine matching logic."""

    def setup_method(self):
        self.engine = RuleEngineAgent()

    def test_general_rules_loaded(self):
        """General rules should be loaded from YAML."""
        packs = self.engine.rule_packs
        assert len(packs) > 0, "At least one rule pack should be loaded"

    def test_keyword_match_on_chinese_text(self):
        """Should match Chinese keywords in contract text."""
        text = """
        甲方有权在合同期内随时自动续约，无需乙方同意。
        违约金为合同总额的50%。
        """
        matches = self.engine.check(text, jurisdiction="CN", contract_type="general")
        # Should find at least the auto-renewal keyword
        match_names = [m.name for m in matches]
        assert len(matches) >= 1, f"Expected at least 1 match, got {len(matches)}"

    def test_no_match_on_clean_text(self):
        """Should return no matches for benign text."""
        text = "这是一段普通的文字，没有任何合同条款内容。天气很好。"
        matches = self.engine.check(text, jurisdiction="CN", contract_type="general")
        assert len(matches) == 0, f"Expected 0 matches, got {len(matches)}: {[m.name for m in matches]}"

    def test_lease_rules_match(self):
        """Lease rules should match lease-specific keywords."""
        text = """
        租赁期间，出租方有权根据市场情况调整租金，承租方不得拒绝。
        押金在合同结束后由出租方决定是否退还。
        承租方如需提前退租，须支付剩余租期全部租金作为违约金。
        """
        matches = self.engine.check(text, jurisdiction="CN", contract_type="lease")
        assert len(matches) >= 1, "Should match lease rules"

    def test_nda_rules_match(self):
        """NDA rules should match confidentiality keywords."""
        text = """
        接收方应对所有保密信息承担永久保密义务。
        如有违反，接收方应赔偿一切损失。
        """
        matches = self.engine.check(text, jurisdiction="CN", contract_type="nda")
        assert len(matches) >= 1, "Should match NDA rules"

    def test_sales_rules_match(self):
        """Sales rules should match product quality keywords."""
        text = """
        买方应在收到货物后付款。卖方不承担运输损失。
        本合同不设退货条款。
        """
        matches = self.engine.check(text, jurisdiction="CN", contract_type="sales")
        assert len(matches) >= 1, "Should match sales rules"

    def test_service_rules_match(self):
        """Service rules should match SLA keywords."""
        text = """
        乙方提供技术服务，服务完成后甲方应支付全部费用。
        项目成果知识产权归乙方所有。
        """
        matches = self.engine.check(text, jurisdiction="CN", contract_type="service")
        assert len(matches) >= 1, "Should match service rules"

    def test_match_returns_correct_structure(self):
        """Each match should have required fields."""
        text = "甲方有权自动续约，合同自动延期。"
        matches = self.engine.check(text, jurisdiction="CN", contract_type="general")
        for match in matches:
            assert match.rule_id, "Match should have rule_id"
            assert match.severity in ("high", "medium", "low"), f"Invalid severity: {match.severity}"
            assert match.name, "Match should have name"
            assert match.description, "Match should have description"
