import hmac
import hashlib
import json
import logging
import httpx
from typing import Dict, Any, Optional

from src.config import settings

logger = logging.getLogger(__name__)

class SecurityService:
    """Handles HMAC signatures for webhooks and request authentication."""

    def sign_payload(self, payload_bytes: bytes, secret: Optional[str] = None) -> str:
        sec = (secret or settings.WEBHOOK_SECRET).encode("utf-8")
        signature = hmac.new(sec, payload_bytes, hashlib.sha256).hexdigest()
        return f"sha256={signature}"

    async def send_webhook_callback(self, callback_url: str, job_data: Dict[str, Any]):
        """Dispatches HMAC-signed completion payload to callback URL (Integration Standard #3)."""
        payload_bytes = json.dumps(job_data).encode("utf-8")
        signature = self.sign_payload(payload_bytes)
        headers = {
            "Content-Type": "application/json",
            "X-IncuBrix-Signature": signature
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(callback_url, content=payload_bytes, headers=headers)
                logger.info(f"Dispatched webhook to {callback_url}, response status: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to dispatch webhook to {callback_url}: {e}")

security_service = SecurityService()
