"""Sample module used by the token-optimizer tests."""
import json


class Cart:
    """A shopping cart."""

    def __init__(self):
        self.items = []

    def add(self, name: str, price: float,
            qty: int = 1) -> None:
        """Add an item."""
        self.items.append({"name": name, "price": price, "qty": qty})

    def total(self) -> float:
        return sum(i["price"] * i["qty"] for i in self.items)


@staticmethod
def helper(x):
    return x * 2


def to_json(cart: Cart) -> str:
    """Serialise a cart."""
    return json.dumps(cart.items)
