#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import unittest
from typing import List, Dict, Optional

import time_machine
from datetime import datetime
from os import path

import mock
from fritzconnection import FritzConnection
from mock.mock import MagicMock

import unuCharger
from unuCharger import createCharger



class TestUnuCharger(unittest.TestCase):

    def defaultTest(self, fc:FritzConnection, testtime:datetime, startTimes:Optional[List[Dict[str,str]]] = []):
        setFile = "testSettings.json"

        if not path.exists(setFile):
            setFile = "test/" + setFile

        with open(setFile) as sFile:
            settings = json.load(sFile)

        settings["Charger"][0]["startTimes"] = startTimes
        uc = createCharger(fc, settings["Charger"][0])

        powerSeq = [
            316350, 316350, 316350, 316350, 317000, 317000, 317000, 317000, 316710, 316710,
            316710, 316710, 315780, 315780, 315780, 315780, 316070, 316070, 316070, 315990,
            315990, 305120, 305120, 294610, 294610, 0, 0]
        mockgetCont = MagicMock(side_effect=powerSeq)
        uc._execGetContent = mockgetCont

        expectedStatus = [unuCharger.Charger.CHARGING] * 24
        expectedStatus.append(unuCharger.Charger.CHARGED)
        expectedStatus.append(unuCharger.Charger.NOT_CHARGING)

        with time_machine.travel(testtime):
            for i, eStatus in enumerate(expectedStatus):
                self.assertEqual(eStatus, uc.evaluate(), f"Failed on input {i}")


    @mock.patch('unuCharger.FritzConnection')
    def test_UC(self, fc):
        self.defaultTest(fc,datetime.now().astimezone())


    @mock.patch('unuCharger.FritzConnection')
    def test_UC_with_wait(self, fc):
        testtime = datetime.strptime("01/01/2025 0:15","%m/%d/%Y %H:%M").astimezone()
        startTimes = [{ "start": "9:50", "end": "11:30"},
                      { "start": "23:30", "end": "1:00" }]
        self.defaultTest(fc,testtime,startTimes)

    @mock.patch('unuCharger.FritzConnection')
    def test_UC_in_withWait(self, fc):
        """ Check that WAITING is working and loading starts in starting period
        """
        setFile = "testSettings.json"
        if not path.exists(setFile):
            setFile = "test/" + setFile

        with open(setFile) as sFile:
            settings = json.load(sFile)

        uc = createCharger(fc, settings["Charger"][0])

        powerSeq = [ 0, 0, 0, 317000, 0, 0, 0, 0 ]
        expectedStatus = [unuCharger.Charger.NOT_CHARGING] * 3 + [unuCharger.UnuCharger.WAITING] * 4
        mockgetCont = MagicMock(side_effect=powerSeq)
        uc._execGetContent = mockgetCont

        # check that waiting status is reached
        with time_machine.travel(datetime.strptime("01/01/2025 9:00", "%m/%d/%Y %H:%M").astimezone()):
            for i, eStatus in enumerate(expectedStatus):
                self.assertEqual(eStatus, uc.evaluate(), f"Failed on input {i}")
            assert(time_machine.time() - uc.startTime > 100, "start time not set correctly")

        powerSeq = [
            316350, 316350, 316350, 316350, 317000, 317000, 317000, 317000, 316710, 316710,
            316710, 316710, 315780, 315780, 315780, 315780, 316070, 316070, 316070, 315990,
            315990, 305120, 305120, 294610, 294610, 0, 0]
        expectedStatus = [unuCharger.Charger.CHARGING] * 24
        expectedStatus.append(unuCharger.Charger.CHARGED)
        expectedStatus.append(unuCharger.Charger.NOT_CHARGING)

        mockgetCont = MagicMock(side_effect=powerSeq)
        uc._execGetContent = mockgetCont

        # now move us into the start loading time period
        # check that we start charging
        with time_machine.travel(datetime.strptime("01/01/2025 10:00", "%m/%d/%Y %H:%M").astimezone()):
            for i, eStatus in enumerate(expectedStatus):
                self.assertEqual(eStatus, uc.evaluate(), f"Failed on input {i}")

                dt= time_machine.time() - uc.startTime
                assert(dt > 3600 and dt < 36200, "start time not set correctly 2")


if __name__ == '__main__':
    unittest.main()