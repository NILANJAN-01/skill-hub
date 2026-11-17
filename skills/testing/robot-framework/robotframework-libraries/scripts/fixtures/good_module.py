from robot.api import logger
from robot.api.deco import keyword
from robot.api.types import Secret


@keyword
def log_in(user: str, token: Secret) -> None:
    """Log in with a service account.

    Args:
        user: Account name.
        token: API token.
    """
    logger.info(f"login {user}")


def not_a_keyword_because_decorators_are_used(x):
    return x
