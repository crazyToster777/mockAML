import allure
import pytest
from pydantic import ValidationError

from src.models.transaction import AMLVerificationResult, RiskLevel, Transaction, TransactionType
from tests.factories import make_aml_result, make_transaction


@allure.epic("Data Models")
@allure.feature("Transaction Model")
@pytest.mark.unit
class TestTransactionModel:
    @allure.story("Account ID normalisation")
    @allure.title("account_id is uppercased automatically")
    def test_account_id_uppercased(self):
        txn = make_transaction(account_id="acct123456")
        assert txn.account_id == "ACCT123456"

    @allure.story("Account ID normalisation")
    @allure.title("counterparty_account_id is uppercased automatically")
    def test_counterparty_uppercased(self):
        txn = make_transaction(counterparty_account_id="acct999999")
        assert txn.counterparty_account_id == "ACCT999999"

    @allure.story("Account ID validation")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("account_id shorter than 6 chars raises ValidationError")
    def test_account_id_too_short(self):
        with pytest.raises(ValidationError):
            Transaction(
                account_id="A1",
                counterparty_account_id="ACCT000002",
                amount_usd="500.00",
                transaction_type=TransactionType.ACH,
            )

    @allure.story("Auto-generated fields")
    @allure.title("transaction_id is auto-generated as UUID")
    def test_transaction_id_auto_generated(self):
        txn1 = make_transaction()
        txn2 = make_transaction()
        assert txn1.transaction_id != txn2.transaction_id
        assert len(txn1.transaction_id) == 36  # UUID4 format

    @allure.story("Amount validation")
    @allure.title("Amount of zero raises ValidationError")
    def test_zero_amount_raises(self):
        with pytest.raises(ValidationError):
            Transaction(
                account_id="ACCT000001",
                counterparty_account_id="ACCT000002",
                amount_usd="0.00",
                transaction_type=TransactionType.CASH_DEPOSIT,
            )


@allure.epic("Data Models")
@allure.feature("AML Verification Result")
@pytest.mark.unit
class TestAMLVerificationResult:
    @allure.story("Suspicious flag")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("HIGH risk → is_suspicious is True")
    def test_is_suspicious_high(self):
        result = make_aml_result(risk_level=RiskLevel.HIGH)
        assert result.is_suspicious is True

    @allure.story("Suspicious flag")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("BLOCKED risk → is_suspicious is True")
    def test_is_suspicious_blocked(self):
        result = make_aml_result(risk_level=RiskLevel.BLOCKED)
        assert result.is_suspicious is True

    @allure.story("Suspicious flag")
    @allure.title("LOW risk → is_suspicious is False")
    def test_is_suspicious_low(self):
        result = make_aml_result(risk_level=RiskLevel.LOW)
        assert result.is_suspicious is False

    @allure.story("Suspicious flag")
    @allure.title("MEDIUM risk → is_suspicious is False")
    def test_is_suspicious_medium(self):
        result = make_aml_result(risk_level=RiskLevel.MEDIUM)
        assert result.is_suspicious is False

    @allure.story("Auto-generated fields")
    @allure.title("result_id is auto-generated and unique")
    def test_result_id_unique(self):
        r1 = make_aml_result()
        r2 = make_aml_result()
        assert r1.result_id != r2.result_id
