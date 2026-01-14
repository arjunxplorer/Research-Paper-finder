"""Circuit breaker for external API resilience."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for an external service."""
    
    name: str
    failure_threshold: int = 3
    success_threshold: int = 2
    timeout_seconds: int = 60
    
    # State tracking
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    
    def record_success(self) -> None:
        """Record a successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                # Service recovered
                self._close()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test
            self._open()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._open()
    
    def is_available(self) -> bool:
        """Check if requests should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = datetime.utcnow() - self.last_failure_time
                if elapsed > timedelta(seconds=self.timeout_seconds):
                    # Try half-open
                    self._half_open()
                    return True
            return False
        
        # Half-open: allow some requests
        return True
    
    def _close(self) -> None:
        """Close the circuit (normal operation)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
    
    def _open(self) -> None:
        """Open the circuit (reject requests)."""
        self.state = CircuitState.OPEN
        self.success_count = 0
    
    def _half_open(self) -> None:
        """Half-open the circuit (test recovery)."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0


# Global circuit breakers for each source
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(source_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for a source."""
    if source_name not in _circuit_breakers:
        _circuit_breakers[source_name] = CircuitBreaker(name=source_name)
    return _circuit_breakers[source_name]


def is_source_available(source_name: str) -> bool:
    """Check if a source is available."""
    cb = get_circuit_breaker(source_name)
    return cb.is_available()


def record_source_success(source_name: str) -> None:
    """Record successful request to a source."""
    cb = get_circuit_breaker(source_name)
    cb.record_success()


def record_source_failure(source_name: str) -> None:
    """Record failed request to a source."""
    cb = get_circuit_breaker(source_name)
    cb.record_failure()


def get_all_breaker_states() -> dict[str, dict]:
    """Get states of all circuit breakers."""
    return {
        name: {
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None,
        }
        for name, cb in _circuit_breakers.items()
    }

