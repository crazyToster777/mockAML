import structlog
import httpx

from src.config import Settings, settings as default_settings
from src.models.transaction import AMLVerificationResult, Transaction

logger = structlog.get_logger(__name__)


class AlertService:
    def __init__(self, cfg: Settings = default_settings):
        self._cfg = cfg

    def send_alert(self, transaction: Transaction, result: AMLVerificationResult) -> None:
        payload = {
            "transaction_id": transaction.transaction_id,
            "account_id": transaction.account_id,
            "risk_level": result.risk_level.value,
            "triggered_rules": result.triggered_rules,
            "amount_usd": str(result.amount_usd),
            "notes": result.notes,
        }
        if self._cfg.alert_log_only:
            logger.warning("aml_alert_triggered", **payload)
            return
        try:
            resp = httpx.post(self._cfg.alert_webhook_url, json=payload, timeout=5.0)
            resp.raise_for_status()
            logger.info("alert_webhook_sent", status=resp.status_code)
        except httpx.HTTPError as exc:
            # Alert failure must not crash the verifier
            logger.error("alert_webhook_failed", error=str(exc))
