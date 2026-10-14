"""
test_pricing.py — Test suite for the pricing module.

Before the bug fix:
  - test_no_discount FAILS with ZeroDivisionError (discount_rate=0 → division by zero)
  - test_batch_discount_isolation FAILS due to mutable default arg

After the bug fix:
  - All tests pass.
"""

import unittest
from pricing import apply_discount, calculate_final_price, batch_discount


class TestApplyDiscount(unittest.TestCase):

    def test_no_discount(self):
        """0% discount should return the original price (not raise ZeroDivisionError)."""
        # BUG: discount_rate=0.0 causes ZeroDivisionError before fix
        result = apply_discount(100.0, 0.0)
        self.assertEqual(result, 100.0)

    def test_half_discount(self):
        """50% discount should return half the price."""
        result = apply_discount(200.0, 0.5)
        self.assertEqual(result, 100.0)

    def test_full_discount(self):
        """100% discount should return 0.0."""
        result = apply_discount(50.0, 1.0)
        self.assertEqual(result, 0.0)

    def test_small_discount(self):
        """10% discount on $100 should give $90."""
        result = apply_discount(100.0, 0.1)
        self.assertAlmostEqual(result, 90.0, places=2)

    def test_negative_price_raises(self):
        """Negative prices should raise ValueError."""
        with self.assertRaises(ValueError):
            apply_discount(-10.0, 0.5)


class TestCalculateFinalPrice(unittest.TestCase):

    def test_standard_discount(self):
        result = calculate_final_price(100.0, 0.2)
        self.assertEqual(result['final_price'], 80.0)
        self.assertEqual(result['discount_amount'], 20.0)

    def test_no_discount(self):
        result = calculate_final_price(150.0, 0.0)
        self.assertEqual(result['final_price'], 150.0)

    def test_full_discount(self):
        result = calculate_final_price(75.0, 1.0)
        self.assertEqual(result['final_price'], 0.0)

    def test_invalid_discount_rate(self):
        with self.assertRaises(ValueError):
            calculate_final_price(100.0, 1.5)

    def test_invalid_negative_rate(self):
        with self.assertRaises(ValueError):
            calculate_final_price(100.0, -0.1)


class TestBatchDiscount(unittest.TestCase):

    def test_batch_basic(self):
        """Basic batch discount should produce correct count of results."""
        result = batch_discount([100.0, 200.0], 0.1)
        self.assertEqual(len(result), 2)

    def test_batch_discount_isolation(self):
        """Each call to batch_discount should NOT accumulate previous results."""
        result1 = batch_discount([100.0], 0.1)
        result2 = batch_discount([200.0], 0.1)
        # With the mutable default arg bug, result2 will contain BOTH items
        self.assertEqual(len(result2), 1,
                         "Mutable default arg bug: result2 accumulated result1's items")


if __name__ == '__main__':
    unittest.main()
