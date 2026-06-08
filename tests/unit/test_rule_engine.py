import allure
import pytest

from src.aml.rules import (
    AmountThresholdRule,
    BlacklistRule,
    RuleEngine,
    RuleResult,
    StructuringRule,
    VelocityRule,
)
from src.models.transaction import RiskLevel
from tests.factories import make_transaction


@allure.epic("AML Rules Engine")
@allure.feature("Risk Aggregation")
@pytest.mark.unit
class TestRiskAggregation:
    @allure.story("BLOCKED wins")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("BLOCKED always wins over HIGH, MEDIUM, LOW")
    def test_blocked_wins_over_all(self):
        results = [
            RuleResult(triggered=True, rule_name="r1", risk_contribution=RiskLevel.BLOCKED),
            RuleResult(triggered=True, rule_name="r2", risk_contribution=RiskLevel.HIGH),
            RuleResult(triggered=False, rule_name="r3", risk_contribution=RiskLevel.MEDIUM),
            RuleResult(triggered=False, rule_name="r4", risk_contribution=RiskLevel.LOW),
        ]
        assert RuleEngine._aggregate_risk(results) == RiskLevel.BLOCKED

    @allure.story("HIGH over MEDIUM")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("HIGH wins over MEDIUM and LOW")
    def test_high_over_medium(self):
        results = [
            RuleResult(triggered=True, rule_name="r1", risk_contribution=RiskLevel.HIGH),
            RuleResult(triggered=True, rule_name="r2", risk_contribution=RiskLevel.MEDIUM),
            RuleResult(triggered=False, rule_name="r3", risk_contribution=RiskLevel.LOW),
        ]
        assert RuleEngine._aggregate_risk(results) == RiskLevel.HIGH

    @allure.story("All LOW")
    @allure.title("All LOW rules → aggregate risk is LOW")
    def test_all_low(self):
        results = [
            RuleResult(triggered=False, rule_name="r1", risk_contribution=RiskLevel.LOW),
            RuleResult(triggered=False, rule_name="r2", risk_contribution=RiskLevel.LOW),
        ]
        assert RuleEngine._aggregate_risk(results) == RiskLevel.LOW


@allure.epic("AML Rules Engine")
@allure.feature("Rule Engine Evaluate")
@pytest.mark.unit
class TestRuleEngineEvaluate:
    @allure.story("Clean transaction")
    @allure.title("Clean transaction produces LOW risk with no triggered rules")
    def test_evaluate_clean_transaction(self):
        engine = RuleEngine(rules=[AmountThresholdRule(), VelocityRule()])
        txn = make_transaction(amount_usd=500.0)
        result = engine.evaluate(txn, [])

        assert result.risk_level == RiskLevel.LOW
        assert result.triggered_rules == []
        assert result.transaction_id == txn.transaction_id
        assert result.account_id == txn.account_id

    @allure.story("Triggered rules listed")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Triggered rule names appear in result.triggered_rules")
    def test_evaluate_returns_correct_rule_names(self):
        engine = RuleEngine(rules=[AmountThresholdRule(), VelocityRule()])
        txn = make_transaction(amount_usd=15_000.0)
        result = engine.evaluate(txn, [])

        assert "amount_threshold" in result.triggered_rules
        assert "velocity" not in result.triggered_rules

    @allure.story("Notes joined")
    @allure.title("Notes from multiple triggered rules are joined with '; '")
    def test_evaluate_notes_joined(self):
        engine = RuleEngine(rules=[
            AmountThresholdRule(threshold_usd=1_000.0),
            BlacklistRule(cfg=None),
        ])
        txn = make_transaction(amount_usd=5_000.0, counterparty_account_id="SANCTIONED001")
        result = engine.evaluate(txn, [])

        assert ";" in result.notes
        assert len(result.triggered_rules) == 2

    @allure.story("Amount USD preserved")
    @allure.title("Result carries the original transaction amount")
    def test_evaluate_amount_preserved(self):
        engine = RuleEngine(rules=[AmountThresholdRule()])
        txn = make_transaction(amount_usd=1_234.56)
        result = engine.evaluate(txn, [])
        assert result.amount_usd == txn.amount_usd

    @allure.story("Blacklisted transaction")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("Blacklisted counterparty → BLOCKED risk in result")
    def test_evaluate_blacklisted_gives_blocked(self):
        engine = RuleEngine(rules=[BlacklistRule(cfg=None)])
        txn = make_transaction(counterparty_account_id="TERROR_FINANCE_003")
        result = engine.evaluate(txn, [])

        assert result.risk_level == RiskLevel.BLOCKED
        assert "blacklist" in result.triggered_rules
