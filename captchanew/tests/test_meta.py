import re
import unittest

from captchanew.meta import __version__


class TestCogMeta(unittest.TestCase):
    def test_version_is_semantic(self):
        match = re.match(
            r"^([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?(\.dev(0|[1-9][0-9]*))?$",
            __version__,
        )
        self.assertIsNotNone(match)
