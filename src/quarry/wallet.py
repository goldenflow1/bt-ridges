"""Inference budget: a hard cap from the environment, per-phase caps, reservations and cost provenance.

Every model attempt reserves its pre-call estimate. The reservation is then settled as:
- "provider": the response reported its cost;
- "estimate": the response reported token usage but no cost (priced from the table, labelled as such);
- "unknown":  no usable report (e.g. a timeout after sending); the reservation stays consumed;
- "none":     evidence of no charge (connection refused, request rejected with an error response); released.
Spending checks use everything consumed, including unknown reservations; reports keep the categories apart.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict, Iterator, Optional, Tuple

DEFAULT_CAP_USD = 0.29
SPENDABLE_SHARE = 0.9
# (input, output) USD per 1M tokens. Unknown models fall back to a conservative price.
FALLBACK_PRICE = (3.0, 15.0)


class BudgetExhausted(Exception):
    """Raised when a call would exceed the budget, or the provider refused on cost grounds."""


def read_cap_env(environ: Optional[dict] = None) -> float:
    env = os.environ if environ is None else environ
    try:
        value = float(str(env.get("RIDGES_MAX_COST_USD", "")).strip())
    except ValueError:
        return DEFAULT_CAP_USD
    return value if value > 0 else DEFAULT_CAP_USD


class Reservation:
    def __init__(self, amount: float, phase: Optional[str]):
        self.amount = amount
        self.phase = phase
        self.settled = False


class Wallet:
    def __init__(self, cap_usd: float, prices: Optional[Dict[str, Tuple[float, float]]] = None):
        self.cap = float(cap_usd)
        self.spendable = self.cap * SPENDABLE_SHARE
        self.spent = False
        self.prices = dict(prices or {})
        self.provider_usd = 0.0
        self.estimate_usd = 0.0
        self.unknown_usd = 0.0  # reservations kept for attempts whose cost is unknown
        self.estimated_calls = 0
        self.unknown_attempts = 0
        self.pending_usd = 0.0  # reservations not yet settled
        self._phase_name: Optional[str] = None
        self._phase_cap: Optional[float] = None
        self._phase_spent = 0.0
        self.by_phase: Dict[str, float] = {}

    @classmethod
    def from_env(cls, environ: Optional[dict] = None, prices: Optional[dict] = None) -> Wallet:
        return cls(read_cap_env(environ), prices)

    # -------------------------------------------------------------- amounts

    @property
    def consumed_usd(self) -> float:
        """Everything that counts against the budget: reported, estimated and unknown-but-reserved."""
        return self.provider_usd + self.estimate_usd + self.unknown_usd

    @property
    def spent_usd(self) -> float:  # kept for callers that only need one number for budget decisions
        return self.consumed_usd

    @property
    def accounting_complete(self) -> bool:
        return self.unknown_attempts == 0

    def price(self, model: str) -> Tuple[float, float]:
        return self.prices.get(model, FALLBACK_PRICE)

    def estimate(self, model: str, prompt_tokens: int, max_tokens: int) -> float:
        price_in, price_out = self.price(model)
        return (prompt_tokens * price_in + max_tokens * price_out) / 1_000_000

    def remaining(self) -> float:
        used = self.consumed_usd + self.pending_usd
        left = self.spendable - used
        if self._phase_cap is not None:
            left = min(left, self._phase_cap - self._phase_spent)
        return max(0.0, left)

    def can_afford(self, estimate_usd: float) -> bool:
        return not self.spent and estimate_usd <= self.remaining()

    def ensure(self, estimate_usd: float) -> None:
        if self.spent:
            raise BudgetExhausted("budget already exhausted")
        if not self.can_afford(estimate_usd):
            raise BudgetExhausted(f"estimated ${estimate_usd:.4f} exceeds remaining ${self.remaining():.4f}")

    # -------------------------------------------------------------- attempt lifecycle

    def reserve(self, estimate_usd: float) -> Reservation:
        """Reserve an attempt's estimate before sending it; refuses when it does not fit."""
        self.ensure(estimate_usd)
        self.pending_usd += estimate_usd
        self._phase_spent += estimate_usd
        return Reservation(estimate_usd, self._phase_name)

    def _close(self, reservation: Reservation) -> None:
        if reservation.settled:
            raise ValueError("reservation already settled")
        reservation.settled = True
        self.pending_usd = max(0.0, self.pending_usd - reservation.amount)
        if reservation.phase == self._phase_name:
            self._phase_spent -= reservation.amount

    def _book(self, reservation: Reservation, amount: float) -> None:
        if reservation.phase == self._phase_name:
            self._phase_spent += amount
        if reservation.phase:
            self.by_phase[reservation.phase] = self.by_phase.get(reservation.phase, 0.0) + amount

    def settle(self, reservation: Reservation, model: str, usage: Optional[dict]) -> Tuple[Optional[float], str]:
        """Replace the reservation with the reported cost, or a labelled usage-based estimate, or keep it as unknown."""
        self._close(reservation)
        usage = usage if isinstance(usage, dict) else {}
        cost = usage.get("cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
            self.provider_usd += float(cost)
            self._book(reservation, float(cost))
            return float(cost), "provider"
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if isinstance(prompt, int) and isinstance(completion, int):
            price_in, price_out = self.price(model)
            estimated = (prompt * price_in + completion * price_out) / 1_000_000
            self.estimate_usd += estimated
            self.estimated_calls += 1
            self._book(reservation, estimated)
            return estimated, "estimate"
        return self.keep_unknown(reservation, already_closed=True)

    def keep_unknown(self, reservation: Reservation, already_closed: bool = False) -> Tuple[Optional[float], str]:
        """No usable report (e.g. timeout after sending): the reservation stays consumed; the real cost is unknown."""
        if not already_closed:
            self._close(reservation)
        self.unknown_usd += reservation.amount
        self.unknown_attempts += 1
        self._book(reservation, reservation.amount)
        return None, "unknown"

    def release(self, reservation: Reservation) -> Tuple[Optional[float], str]:
        """Evidence of no charge (never sent, or rejected with an error response): give the reservation back."""
        self._close(reservation)
        return 0.0, "none"

    def charge(self, model: str, usage: Optional[dict]) -> float:
        """One-step reserve-and-settle for a completed response (no pre-call reservation available)."""
        reservation = Reservation(0.0, self._phase_name)
        cost, _source = self.settle(reservation, model, usage)
        return cost if cost is not None else 0.0

    def mark_spent(self) -> None:
        self.spent = True

    @contextmanager
    def phase(self, name: str, cap_usd: float) -> Iterator[Wallet]:
        """Limit spending to `cap_usd` inside the block (nested phases are not supported)."""
        saved = (self._phase_name, self._phase_cap, self._phase_spent)
        self._phase_name, self._phase_cap, self._phase_spent = name, float(cap_usd), 0.0
        try:
            yield self
        finally:
            self._phase_name, self._phase_cap, self._phase_spent = saved

    def summary(self) -> Dict[str, object]:
        return {
            "provider_usd": round(self.provider_usd, 6),
            "estimate_usd": round(self.estimate_usd, 6),
            "estimated_calls": self.estimated_calls,
            "unknown_attempts": self.unknown_attempts,
            "unknown_reserved_usd": round(self.unknown_usd, 6),
            "accounted_usd": round(self.provider_usd + self.estimate_usd, 6),
            "consumed_usd": round(self.consumed_usd, 6),
            "cost_estimated": self.estimated_calls > 0,
            "accounting_complete": self.accounting_complete,
        }


def is_temporary_budget_refusal(status: int, body: str, headers: Optional[Dict[str, str]] = None) -> bool:
    """A 402 that only says spending is momentarily reserved by requests still in flight, or that names a time
    to retry: worth retrying within the call, and not evidence that the cap was reached (H-LLM-03)."""
    if status != 402:
        return False
    text = (body or "").lower()
    return any(marker in text for marker in ("in_flight", "in-flight", "inflight")) or "retry-after" in (headers or {})


def is_budget_refusal(status: int, body: str) -> bool:
    """True when a provider response means the cost cap was hit (never worth retrying). Check
    is_temporary_budget_refusal first: a temporary 402 is not a cap."""
    if status == 402:
        return True
    text = (body or "").lower()
    return status in (400, 403, 429) and any(
        marker in text for marker in ("budget", "cost cap", "max cost", "spend limit", "insufficient credit")
    )
