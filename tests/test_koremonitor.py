import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from koremonitor import KoreMonitor  # noqa


class TestInit(unittest.TestCase):
    def test_init(self):
        koremonitor = KoreMonitor()
        self.assertEqual(koremonitor.cores, {})
