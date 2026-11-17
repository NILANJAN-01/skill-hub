from robot.api.deco import keyword, library, not_keyword
from robot.libraries.BuiltIn import BuiltIn
from robot.utils import is_string


@library(version="1.0", auto_keywords=True)
class OrdersLibrary:

    def connect(self, user, password: str):
        print("connecting", user)
        BuiltIn().get_variable_value("${URL}", default="http://localhost")

    @keyword("Order ${order_id: int} should be ${status}")
    def order_status(self, order_id: int, status: str):
        """Check the order status."""
        try:
            pass
        except BaseException:
            pass

    async def wait_for_order(self, order_id: int) -> None:
        """Wait until the order exists."""

    @not_keyword
    def helper(self):
        return is_string("x")

    def _private(self):
        pass
