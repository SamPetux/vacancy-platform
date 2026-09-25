"""Salary line formatting for editorial posts."""

from __future__ import annotations


def format_salary_line(
    salary_from: float | int | None,
    salary_to: float | int | None,
    *,
    currency: str | None = "RUB",
) -> str | None:
    """Compact human salary: «120–160 тыс. ₽» / «от 95 тыс. ₽»."""
    low = _to_int(salary_from)
    high = _to_int(salary_to)
    if low is None and high is None:
        return None
    symbol = "₽" if (currency or "RUB").upper() in {"RUB", "RUR"} else (currency or "₽")
    if low is not None and high is not None:
        if low == high:
            return f"{_thousands(low)} тыс. {symbol}"
        return f"{_thousands(low)}–{_thousands(high)} тыс. {symbol}"
    if low is not None:
        return f"от {_thousands(low)} тыс. {symbol}"
    assert high is not None
    return f"до {_thousands(high)} тыс. {symbol}"


def _to_int(value: float | int | None) -> int | None:
    if value is None:
        return None
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _thousands(amount: int) -> int:
    if amount >= 1000:
        return int(round(amount / 1000))
    return amount
