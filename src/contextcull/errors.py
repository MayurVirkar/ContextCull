"""Standard exceptions and status definitions for TEP."""


class TepError(Exception):
    """Base exception for all TEP operations."""


class BudgetUnsafeError(TepError):
    """Raised when the requested token budget cannot safely contain mandatory units."""

    def __init__(
        self,
        requested_tokens: int,
        minimum_safe_tokens: int,
        missing_atoms: list[str] | None = None,
        mandatory_unit_ids: list[str] | None = None,
        message: str | None = None,
    ) -> None:
        self.requested_tokens = requested_tokens
        self.minimum_safe_tokens = minimum_safe_tokens
        self.missing_atoms = missing_atoms or []
        self.mandatory_unit_ids = mandatory_unit_ids or []
        msg = (
            message
            or f"TARGET_BUDGET_UNSAFE: requested_tokens={requested_tokens}, "
            f"minimum_safe_tokens={minimum_safe_tokens}"
        )
        super().__init__(msg)


class InvariantViolationError(TepError):
    """Raised when invariant validation fails on candidate or emitted output."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__(f"Invariant validation failed: {'; '.join(violations)}")


class SourceMapError(TepError):
    """Raised when an offset or span lookup is invalid."""


class ParseError(TepError):
    """Raised when block or structural parsing fails."""
