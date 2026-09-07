import unittest
from decimal import Decimal


def calculate_margin(revenue: Decimal, quantity: Decimal, average_cost: Decimal) -> Decimal:
    return revenue - quantity * average_cost


def calculate_forecast(confirmed_dispatch_qty: Decimal, horizon_days: int) -> Decimal:
    return confirmed_dispatch_qty / Decimal("90") * Decimal(str(horizon_days))


class CommercialRuleTests(unittest.TestCase):
    def test_margin_uses_historical_cost_not_language_model(self):
        self.assertEqual(calculate_margin(Decimal("150"), Decimal("10"), Decimal("9")), Decimal("60"))

    def test_forecast_is_based_on_confirmed_dispatches(self):
        self.assertEqual(calculate_forecast(Decimal("90"), 30), Decimal("30"))


if __name__ == "__main__":
    unittest.main()
