#!/usr/bin/env python

import os.path
import sys
import time

from fritzconnection import FritzConnection
from typing import Any, List, Dict
import statistics
import json


def warn(strg:str):
    print(strg, file=sys.stderr)


class AbstractCharger:
    CHARGING = 1
    NOT_CHARGING = 0
    CHARGED = -1

    def __init__(self, AIN:str, fritzCon:Any):
        self.fritzCon = fritzCon
        self.AIN = AIN

    def _execGetContent(self, command) -> int:
        """ execute webservice call return content or 0 if no content"""
        try:
            jsn = self.fritzCon.call_http(command, self.AIN)
            # print(f"ret: ------------- {jsn}")
            reti = int(jsn['content'])
        except Exception as error:
            print("An exception occurred:", error)
            reti = 0

        return reti


class Charger(AbstractCharger):

    def __init__(self, name:str, AIN:str, fritzCon:Any, triggerPowerMW:int, statsPoolSize:int = 3,
                       startPowerMW=0, log=False):
        super().__init__(AIN, fritzCon)
        self.name = name
        self.triggerPowerMW = triggerPowerMW
        self.statsPoolSize = statsPoolSize
        self.reads:List[int] = []
        self.startPowerMW = startPowerMW   # only needed for AutoChargers
        self.startTime = time.time()
        self.status = self.NOT_CHARGING
        self.logFile = None
        if log:
            lf =  f"{name}.tab"
            isOldFile =  os.path.exists(lf)
            self.logFile = open(lf,"at", buffering=1)
            if isOldFile and os.path.getsize(lf) > 10000:
                self.logFile.truncate(0)

        warn(f"Batterie monitor created for {name} triggering at {triggerPowerMW/1000:.2f}")

    def evaluate(self):
        if len(self.reads) >= self.statsPoolSize and len(self.reads) > 0:
            self.reads.pop(0)
        power = self._execGetContent("getswitchpower")
        if self.logFile and self.status == self.CHARGING:
            print(f"{self.name}\t{time.time() - self.startTime:.0f}\t{power}",file=self.logFile)

        if self.status != self.CHARGING:
            # remove values below 10 mW so that when new charging starts
            # the low values of disconnected charge do not average out new values
            self.reads = list(filter(lambda v: v > 10, self.reads))
        self.reads.append(power)

        pMedian = statistics.median(self.reads)

        if len(self.reads) < self.statsPoolSize:
            if pMedian < 10:
                self.status = self.NOT_CHARGING
            else:
                if not self.status == self.CHARGING:
                    self.startTime = time.time()
                    self.status = self.CHARGING
            return self.status

        if not self.status == self.CHARGING:
            self.startTime = time.time()
            self.status = self.CHARGING

        # switch off if power threshold is reached
        if pMedian <= self.triggerPowerMW:
            self._execGetContent("setswitchoff")
            print(f"Charged: {self.name}: {self.reads}",file=self.logFile)
            self.reads = []

            self.status = self.CHARGED
        return self.status


class AutoCharger(AbstractCharger):
    """
    Detect which of the chargers to use based on the "StartPowerW" propery of the
    Charger. Compare the power used at the start of the chargng cycle and use
    The charger with the highest Power that iss below StartPowerW.

    """
    def __init__(self, chargers:List[Charger], statsPoolSize:int = 3):
        AIN = chargers[0].AIN
        fritzCon = chargers[0].fritzCon

        for c in chargers:
            if c.AIN != AIN or c.fritzCon != fritzCon:
                raise Exception(f'inconsistent AIN or fritzCon in AutoCharger')

        super().__init__(AIN, fritzCon)

        self.chargers = sorted(chargers, key=lambda c: -c.startPowerMW)
        self.currentCharger = None
        self.statsPoolSize = statsPoolSize
        self.reads: List[int] = []

    def evaluate(self):
        if not self.currentCharger:
            self.currentCharger = self.detectCharger()
            if self.currentCharger:
                return Charger.CHARGING
            else:
                return Charger.NOT_CHARGING

        elif self.currentCharger:
            ret = self.currentCharger.evaluate()
            if ret == Charger.CHARGED or ret == Charger.NOT_CHARGING:
                warn(f"Finished Loading {self.currentCharger.name}")
                self.currentCharger = None
                self.reads = []

            return ret

    def detectCharger(self):
        # filter out low values from disconnected time to compute average correctly
        self.reads = list(filter(lambda v: v > 10, self.reads))
        if len(self.reads) >= self.statsPoolSize:
            self.reads.pop(0)
        power = self._execGetContent("getswitchpower")
        self.reads.append(power)

        if len(self.reads) < self.statsPoolSize:
            return None

        pMedian = statistics.median(self.reads)
        for c in self.chargers:
            if pMedian > c.startPowerMW:
                warn(f"Start Loading {c.name}")
                return c

        # Current Power usage is smaller than smallest charger
        # Let's switch off everything
        self.fritzCon.call_http("setswitchoff", self.AIN)
        return None


class UnuCharger(Charger):
    """
    This Charger recognizes a significant drop in Charging power
    in the last 30% quantile compared to the max of the stats pool.
    """

    def __init__(self, name:str, AIN:str, fritzCon:Any, triggerPowerDiffMW:int, statsPoolSize:int = 3,
                       startPowerMW=260, log=False):
        super().__init__(name, AIN, fritzCon, triggerPowerDiffMW, statsPoolSize, startPowerMW, log)

    def evaluate(self):
        if len(self.reads) >= self.statsPoolSize and len(self.reads) > 0:
            self.reads.pop(0)
        power = self._execGetContent("getswitchpower")
        if self.logFile and self.status == self.CHARGING:
            print(f"{self.name}\t{time.time() - self.startTime:.0f}\t{power}",file=self.logFile)

        if self.status != self.CHARGING:
            # remove values below 10 mW so that when new charging starts
            # the low values of disconnected charge do not average out new values
            self.reads = list(filter(lambda v: v > 10, self.reads))
        self.reads.append(power)

        pMedian = statistics.median(self.reads)

        if len(self.reads) < self.statsPoolSize:
            if pMedian < 10:
                self.status = self.NOT_CHARGING
            else:
                if not self.status == self.CHARGING:
                    self.startTime = time.time()
                    self.status = self.CHARGING
            return self.status

        if not self.status == self.CHARGING:
            self.startTime = time.time()
            self.status = self.CHARGING

        # switch off if power threshold is reached
        pMax = max(self.reads)
        lowest30 = statistics.quantiles(self.reads, n=10)[2]
        if pMax - lowest30 > self.triggerPowerMW:
            self._execGetContent("setswitchoff")
            print(f"Charged: {self.name}: {self.reads}",file=self.logFile)
            self.reads = []

            self.status = self.CHARGED
        return self.status


def createCharger(fc:FritzConnection, json:Dict[str,Any])->Charger:
    AIN = json["AIN"]
    name = json["name"]
    statsPoolSize = json["statsPoolSize"]
    startPower = int(json.get("startPowerW","0") * 1000)
    log = json.get("log",False)

    if json.get("type", None) == "UNU":
        triggerPowerDiffMW = int(json["triggerPowerDiffW"] * 1000)
        return UnuCharger(name, AIN, fc, triggerPowerDiffMW, statsPoolSize, startPower, log)
    else:
        triggerPowerMW = int(json["triggerPowerW"] * 1000)
        return Charger(name, AIN, fc, triggerPowerMW, statsPoolSize, startPower, log)


def createAutoCharger(fc:FritzConnection, json:Dict[str,Any]):
    AIN = json["AIN"]
    statsPoolSize =  json["statsPoolSize"]
    chrgrs = []
    for c in json["Charger"]:
        c["AIN"] = AIN
        chrgrs.append(createCharger(fc, c))

    return AutoCharger(chrgrs, statsPoolSize)



#######################################################
if __name__ == "__main__":

    setFile = "settings.json"
    if len(sys.argv) > 1:
        setFile = sys.argv[1]

    with open(setFile) as sFile:
        settings = json.load(sFile)

    fritzIP = settings["fritzIP"]
    user    = settings["user"]
    passWD  = settings["passWD"]
    freq    = settings["frequencyS"]

    while True:
        try:
            fc = FritzConnection(address=fritzIP, user=user, password=passWD,
                                 use_cache=True)
        except Exception as error:
            time.sleep(30)
            print("Fritzbox not avialable:", error)

    batMonitors:List[Any] = []
    chargerByAIN:Dict[str,Charger] = {}


    for json in settings["Charger"]:
        if "Charger" not in json:
            batMonitors.append(createCharger(fc, json))
        else:
            batMonitors.append(createAutoCharger(fc, json))

    while True:
        for bl in batMonitors:
            bl.evaluate()
        time.sleep(freq)
