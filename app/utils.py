"""Small helpers shared by the whole backend."""
from __future__ import annotations

import math
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Iterable

import numpy as np
import pandas as pd
from fastapi import HTTPException


def is_missing(value: Any) -> bool:
    """True for None / NaN / pd.NA / NaT (i.e. 'no data')."""
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value, Decimal):
        return not value.is_finite()
    if isinstance(value, (float, np.floating)):
        return not math.isfinite(float(value))
    return False


def clean(obj: Any) -> Any:
    """
    Make any object safe for JSON:
      * numpy / pandas types -> plain Python types
      * NaN, +inf, -inf, NaT, pd.NA -> null
    JSON has no NaN/Infinity, and browsers' JSON.parse would fail on them.
    """
    if obj is None or obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    return obj


def success(data: Any, meta: dict | None = None) -> dict:
    """Every successful response has the same shape: {status, data, meta}."""
    return {"status": "success", "data": clean(data), "meta": clean(meta or {})}


def round_or_none(value: Any, digits: int = 2) -> float | None:
    return None if is_missing(value) else round(float(value), digits)


def normalize_choice(value: str | None, allowed: Iterable[str], field: str) -> str | None:
    """Case-insensitive check of a query parameter against a list of allowed values."""
    if value is None or value == "":
        return None
    allowed = list(allowed)
    lookup = {a.lower(): a for a in allowed}
    found = lookup.get(value.strip().lower())
    if found is None:
        raise HTTPException(
            status_code=422,
            detail={"message": f"Invalid value '{value}' for '{field}'.",
                    "allowed_values": allowed},
        )
    return found
