import logging
import time
import json
from typing import Dict, Any

# Setup telemetry logger
logger = logging.getLogger("llm_telemetry_logs")

class TelemetryService:
    def record_metric(self, name: str, value: Any, extra: Dict[str, Any] = None) -> None:
        """Record a structured telemetry metric to llm_telemetry_logs."""
        payload = {
            "metric": name,
            "value": value,
            "timestamp": time.time()
        }
        if extra:
            payload.update(extra)
        logger.info(json.dumps(payload))

telemetry_service = TelemetryService()
