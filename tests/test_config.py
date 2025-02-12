# standard
import unittest

# external
from lnetatmo import ClientAuth

# internal
from netatmo.config import auth_check


class Test_AuthCheck(unittest.TestCase):
    def test_failure(self):
        authentication = ClientAuth(
            clientId="BadID", clientSecret="BadSecret", refreshToken="BadToken"
        )
        self.assertFalse(auth_check(authentication))

    def test_success(self):
        authentication = ClientAuth()
        self.assertTrue(auth_check(authentication))
