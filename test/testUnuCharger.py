#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import unittest

import mock
from mock.mock import MagicMock

import unuCharger
from unuCharger import createCharger



class unuChargerTestCase(unittest.TestCase):

    @mock.patch('unuCharger.FritzConnection')
    def test_UC(self, fc):
        setFile = "testSettings.json"

        with open(setFile) as sFile:
            settings = json.load(sFile)

        uc = createCharger( fc, settings["Charger"][0])

        powerSeq= [
            316350, 316350, 316350, 316350, 317000, 317000, 317000, 317000, 316710, 316710,
            316710, 316710, 315780, 315780, 315780, 315780, 316070, 316070, 316070, 315990,
            315990, 305120, 305120, 294610, 294610, 0, 0]
        mockgetCont = MagicMock(side_effect=powerSeq)

        expectedStatus = [unuCharger.Charger.CHARGING] * 24
        expectedStatus.append(unuCharger.Charger.CHARGED)
        expectedStatus.append(unuCharger.Charger.NOT_CHARGING)

        uc._execGetContent = mockgetCont
        for i, eStatus in enumerate(expectedStatus):
            self.assertEqual(eStatus, uc.evaluate(), f"Failed on {i}")
