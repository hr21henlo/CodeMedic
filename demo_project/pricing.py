"""
pricing.py - Price and discount calculation module.

This module contains two reproducible bugs:

  Bug 1 (Critical): apply_discount() divides by `discount_rate` directly
    when discount_rate == 0.0 (no discount), causing ZeroDivisionError.

  Bug 2 (Medium): batch_discount() uses a mutable default argument `results=[]`,
    causing results to accumulate across calls.
"""


def apply_discount(original_price: float, discount_rate: float) -> float:
    """
    Calculate the discounted price.

    Args:
        original_price: The original price (must be >= 0)
        discount_rate: Discount as a fraction (0.0 = no discount, 1.0 = 100% off)

    Returns:
        The price after discount.

    Bug: Divides by `discount_rate` without checking for zero.
         When discount_rate == 0.0, raises ZeroDivisionError.
    """
    if original_price < 0:
        raise ValueError("Price cannot be negative")

    # BUG: When discount_rate == 0.0, this raises ZeroDivisionError.
    #      The correct formula is: original_price * (1 - discount_rate)
    discount_amount = original_price / discount_rate
    return round(original_price - discount_amount, 2)


def calculate_final_price(original_price: float, discount_rate: float) -> dict:
    """
    Return a breakdown of original price, discount amount, and final price.
    This function is implemented correctly.
    """
    if not (0.0 <= discount_rate <= 1.0):
        raise ValueError(f"discount_rate must be between 0 and 1, got {discount_rate}")

    discount_amount = original_price * discount_rate
    final_price = original_price - discount_amount
    return {
        "original": original_price,
        "discount_rate": discount_rate,
        "discount_amount": round(discount_amount, 2),
        "final_price": round(final_price, 2),
    }


def batch_discount(prices: list, discount_rate: float, results=[]) -> list:
    """
    Apply a discount to a list of prices.

    Bug: 'results=[]' is a mutable default argument — mutations persist
         across function calls, so successive calls accumulate results.
    """
    for price in prices:
        results.append(calculate_final_price(price, discount_rate)["final_price"])
    return results
