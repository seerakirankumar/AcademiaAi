from decimal import Decimal

import pytest

from app.utils import is_missing


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("NaN"), True),
        (Decimal("Infinity"), True),
        ("", False),
        ("\u0394", False),
    ],
)
def test_is_missing_handles_decimal_non_finite_and_text_values(value, expected):
    assert is_missing(value) is expected
