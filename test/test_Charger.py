#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest

import mock
from mock.mock import MagicMock

from unuCharger import Charger


class TestCharger(unittest.TestCase):

    @mock.patch('unuCharger.FritzConnection')
    def testCharger(self, fc):
        chrg = Charger("test", 'AIN', fc, 12000, 5, 15000, False)
        mockgetCont = MagicMock(side_effect=[0,25030, 25030, 25030, 25030,25030,0,0,0,0,0])
        Charger._execGetContent = mockgetCont
        self.assertEqual(0, chrg.evaluate())
        self.assertEqual(1, chrg.evaluate())
        self.assertEqual(1, chrg.evaluate())
        self.assertEqual(1, chrg.evaluate())
        self.assertEqual(1, chrg.evaluate())
        self.assertEqual(1, chrg.evaluate())
        self.assertEqual(1, chrg.evaluate())
        self.assertEqual(1, chrg.evaluate())
        self.assertEqual(-1, chrg.evaluate())
        self.assertEqual(0, chrg.evaluate())


if __name__ == '__main__':
    unittest.main()