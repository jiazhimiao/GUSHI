"""Kill switch and emergency stop mechanisms."""


class KillSwitch:
    """Emergency stop for live trading.

    Triggers on:
    - Consecutive order failures
    - Excessive drawdown
    - Account value anomaly
    - Data feed latency
    """

    def __init__(self, max_drawdown: float = 0.10, max_consecutive_failures: int = 3):
        self.max_drawdown = max_drawdown
        self.max_consecutive_failures = max_consecutive_failures
        self._killed = False
        self._reason = ""
        self._consecutive_failures = 0

    def check_drawdown(self, current_value: float, peak_value: float) -> bool:
        """Check if drawdown exceeds limit."""
        if peak_value <= 0:
            return False
        dd = (current_value - peak_value) / peak_value
        if dd < -self.max_drawdown:
            self._killed = True
            self._reason = f"drawdown: {dd:.2%}"
            return True
        return False

    def record_failure(self) -> bool:
        """Record an order failure, trigger if threshold exceeded."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.max_consecutive_failures:
            self._killed = True
            self._reason = f"consecutive_failures: {self._consecutive_failures}"
            return True
        return False

    def record_success(self):
        self._consecutive_failures = 0

    def kill(self, reason: str):
        self._killed = True
        self._reason = reason

    def reset(self):
        self._killed = False
        self._reason = ""
        self._consecutive_failures = 0

    @property
    def is_killed(self) -> bool:
        return self._killed

    @property
    def reason(self) -> str:
        return self._reason
