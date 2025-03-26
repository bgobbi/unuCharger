#!/usr/bin/env python
# -*- coding: utf-8 -*-
from unuCharger import Charger

from typing import List
import mock
import unittest

class MockAbstractCharger:
    def __init__(self, responseList:List[int] = []):
        self.responseList = responseList

    def _execGetContent(self, command):
        if len(self.responseList) > 0:
            return self.responseList.pop(0)
        else:
            return 0

class unuChargerTestCase(unittest.TestCase):

    @mock.patch('unuCharger.FritzConnection')
    def test_UC(self, fc):
        uc = Charger("test", 'AIN', fc, 12000, 5, 15000, False)
        mockAC = MockAbstractCharger([0,25030, 25030, 25030, 25030,25030,0,0,0,0,0])
        Charger._execGetContent = mockAC._execGetContent
        self.assertEqual(0, uc.evaluate())
        self.assertEqual(1, uc.evaluate())
        self.assertEqual(1, uc.evaluate())
        self.assertEqual(1, uc.evaluate())
        self.assertEqual(1, uc.evaluate())
        self.assertEqual(1, uc.evaluate())
        self.assertEqual(1, uc.evaluate())
        self.assertEqual(1, uc.evaluate())
        self.assertEqual(-1, uc.evaluate())
        self.assertEqual(0, uc.evaluate())
        self.assertEqual(0, uc.evaluate())
