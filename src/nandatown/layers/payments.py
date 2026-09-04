"""Payments layer: a testnet ledger with escrow.

All amounts are strictly positive integer cents. Money is conserved: the
sum of balances plus held escrow never changes after accounts open.
Every movement is an event, and so is every refusal.
"""

from __future__ import annotations

from typing import Any

from . import register


class PaymentError(Exception):
    """A payment was refused: malformed amount, or insufficient funds."""


def validate_amount(cents: Any) -> int:
    """Money is a strictly positive whole number of cents.

    bool is excluded because it subclasses int: True would move a cent.
    """
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise PaymentError(f"amount must be an int, got {cents!r}")
    if cents <= 0:
        raise PaymentError(f"amount must be positive, got {cents}")
    return cents


@register("payments", "ledger.v1")
class Ledger:
    """Balances, transfers, and escrow hold, release, refund."""

    def __init__(self, engine):
        self.engine = engine
        self.balances: dict[str, int] = {}
        self.escrow: dict[str, dict[str, Any]] = {}

    def open_account(self, name: str, cents: int) -> None:
        if isinstance(cents, bool) or not isinstance(cents, int) or cents < 0:
            raise PaymentError(
                f"opening balance must be a whole number of cents,"
                f" got {cents!r}")
        if name not in self.balances:
            self.balances[name] = cents
            self.engine.emit("town", "account_opened", name,
                             {"balance_cents": cents})

    def balance(self, name: str) -> int:
        return self.balances.get(name, 0)

    def total(self) -> int:
        return (sum(self.balances.values())
                + sum(h["cents"] for h in self.escrow.values()
                      if h["state"] == "held"))

    def _reject(self, actor: str, reason: str, detail: dict[str, Any]) -> None:
        self.engine.emit("town", "payment_rejected", actor,
                         dict(detail, reason=reason))

    def transfer(self, frm: str, to: str, cents: int, memo: str) -> None:
        try:
            cents = validate_amount(cents)
        except PaymentError as exc:
            self._reject(frm, str(exc),
                         {"to": to, "cents": repr(cents), "memo": memo})
            raise
        if self.balance(frm) < cents:
            self._reject(frm, "insufficient funds",
                         {"to": to, "cents": cents, "memo": memo})
            raise PaymentError(f"{frm} lacks {cents}")
        self.balances[frm] -= cents
        self.balances[to] = self.balance(to) + cents
        self.engine.emit("town", "payment_settled", memo,
                         {"from": frm, "to": to, "cents": cents})

    def hold(self, frm: str, cents: int, ref: str) -> None:
        if ref in self.escrow:
            raise PaymentError(f"escrow ref {ref} reused")
        try:
            cents = validate_amount(cents)
        except PaymentError as exc:
            self._reject(frm, str(exc), {"cents": repr(cents), "ref": ref})
            raise
        if self.balance(frm) < cents:
            self._reject(frm, "insufficient funds",
                         {"cents": cents, "ref": ref})
            raise PaymentError(f"{frm} lacks {cents}")
        self.balances[frm] -= cents
        self.escrow[ref] = {"from": frm, "cents": cents, "state": "held"}
        self.engine.emit("town", "escrow_held", ref,
                         {"from": frm, "cents": cents})

    def release(self, ref: str, to: str) -> None:
        h = self.escrow.get(ref)
        if h is None or h["state"] != "held":
            raise PaymentError(f"escrow ref {ref} not held")
        h["state"] = "released"
        self.balances[to] = self.balance(to) + h["cents"]
        self.engine.emit("town", "escrow_released", ref,
                         {"to": to, "cents": h["cents"]})
        self.engine.emit("town", "payment_settled", ref,
                         {"from": h["from"], "to": to, "cents": h["cents"],
                          "via": "escrow"})

    def refund(self, ref: str) -> None:
        h = self.escrow.get(ref)
        if h is None or h["state"] != "held":
            raise PaymentError(f"escrow ref {ref} not held")
        h["state"] = "refunded"
        self.balances[h["from"]] += h["cents"]
        self.engine.emit("town", "escrow_refunded", ref,
                         {"to": h["from"], "cents": h["cents"]})
