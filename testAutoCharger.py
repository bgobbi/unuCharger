import json
import unittest
from unittest import mock
from unittest.mock import MagicMock

import unuCharger
from unuCharger import createAutoCharger


class AutoLoaderTest(unittest.TestCase):
    @mock.patch('unuCharger.FritzConnection')
    def __init__(self, name, fc):
        super().__init__(name)
        setFile = "test/testSettings.json"

        with open(setFile) as sFile:
            settings = json.load(sFile)


        self.ACharger = createAutoCharger(fc, settings['Charger'][1])


    def test_AutoLoader(self):
        mockgetContAC = MagicMock(side_effect=[0, 25030, 25030, 25030, 0, 0,
                                             2430, 2430, 2430, 2430, ])
        mockgetContCalvin = MagicMock(side_effect=[10580, 10580, 10580, 0 ])
        mockgetContSCore = MagicMock(side_effect =[2430, 2430, 2430, 2430])


        self.ACharger._execGetContent = mockgetContAC

        self.assertEqual(self.ACharger.chargers[0].name, 'Calvin')
        self.ACharger.chargers[0]._execGetContent = mockgetContCalvin

        self.assertEqual(self.ACharger.chargers[-1].name, 'AG SoundCore')
        self.ACharger.chargers[-1]._execGetContent = mockgetContSCore

        self.assertEqual(unuCharger.Charger.NOT_CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.NOT_CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.NOT_CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())
        self.assertEqual(self.ACharger.currentCharger.name, 'Calvin')

        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.CHARGED, self.ACharger.evaluate())
        self.assertIsNone(self.ACharger.currentCharger)

        self.assertEqual(unuCharger.Charger.NOT_CHARGING, self.ACharger.evaluate())  ## 0
        self.assertEqual(unuCharger.Charger.NOT_CHARGING, self.ACharger.evaluate())  ## 0
        self.assertEqual(unuCharger.Charger.NOT_CHARGING, self.ACharger.evaluate())  ## 2430
        self.assertEqual(unuCharger.Charger.NOT_CHARGING, self.ACharger.evaluate())  ## 2430
        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())      ## 2430
        self.assertEqual(self.ACharger.currentCharger.name, 'AG SoundCore')
        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())
        self.assertEqual(unuCharger.Charger.CHARGING, self.ACharger.evaluate())

if __name__ == '__main__':
    unittest.main()
