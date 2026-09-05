import unittest
from decimal import Decimal


def validate_available_stock(physical_qty: Decimal, reserved_qty: Decimal, requested_delta: Decimal) -> Decimal:
    next_reserved = reserved_qty + requested_delta
    available = physical_qty - next_reserved
    if next_reserved < 0:
        raise ValueError("reserved cannot be negative")
    if available < 0:
        raise ValueError("available stock cannot be negative")
    return available


class InventoryRuleTests(unittest.TestCase):
    def test_prevents_negative_available_stock(self):
        with self.assertRaises(ValueError):
            validate_available_stock(Decimal("5"), Decimal("3"), Decimal("3"))

    def test_accepts_partial_release(self):
        remaining = validate_available_stock(Decimal("5"), Decimal("3"), Decimal("-1"))
        self.assertEqual(remaining, Decimal("3"))


if __name__ == "__main__":
    unittest.main()
