# standard
import logging

# external
# internal
from lnetatmo import ClientAuth


def auth_check(authentication: ClientAuth) -> bool:
    """
    Check successful authentication with Netatmo.

    Refer to README for authentication set up.

    Return True if successful.
    """
    try:
        authentication.renew_token()
    except TypeError as e:
        logging.critical(f"{e}")
        return False
    else:
        return True
