import time
import logging
from typing import Callable, Any, Optional, Tuple
from sqlalchemy.orm import Session

from ott_agent.models.system import ProcessingError, LatencyMeasurement

logger = logging.getLogger(__name__)


class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is OPEN to prevent downstream dependency flooding."""
    pass


class CircuitBreaker:
    """Circuit breaker pattern implementation with monotonic clock measurements."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 10.0,
        max_call_latency_seconds: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.max_call_latency = max_call_latency_seconds

        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.last_failure_time = 0.0

    def execute(self, func: Callable[..., Any], *args, **kwargs) -> Tuple[Any, float]:
        """Execute callable protected by circuit breaker and monotonic timing."""
        now = time.monotonic()

        if self.state == "OPEN":
            if now - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("CircuitBreaker transitioned from OPEN to HALF_OPEN")
            else:
                raise CircuitBreakerOpenException("Circuit breaker is OPEN. Falling back to deterministic mode.")

        start_time = time.monotonic()
        try:
            result = func(*args, **kwargs)
            elapsed_sec = time.monotonic() - start_time

            if elapsed_sec > self.max_call_latency:
                raise TimeoutError(f"Call exceeded maximum allowed latency threshold ({elapsed_sec:.2f}s > {self.max_call_latency}s)")

            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("CircuitBreaker transitioned from HALF_OPEN to CLOSED")

            return result, elapsed_sec * 1000.0
        except Exception as e:
            elapsed_sec = time.monotonic() - start_time
            self.failure_count += 1
            self.last_failure_time = time.monotonic()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(f"CircuitBreaker transitioned to OPEN after {self.failure_count} consecutive failures: {e}")

            raise e


def log_processing_error(db: Session, component: str, error: Exception):
    """Log structured operational processing error to database."""
    pe = ProcessingError(
        component=component,
        error_message=str(error),
        traceback=getattr(error, "__traceback__", None) and str(error.__traceback__)
    )
    db.add(pe)
    db.commit()


def log_latency_measurement(db: Session, operation: str, duration_ms: float):
    """Log structured latency measurement to database."""
    lm = LatencyMeasurement(
        operation=operation,
        duration_ms=duration_ms
    )
    db.add(lm)
    db.commit()
