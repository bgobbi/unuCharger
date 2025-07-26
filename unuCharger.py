#!/usr/bin/env python

import os.path
import sys
import time
import traceback
from datetime import datetime

from fritzconnection import FritzConnection
from typing import Any, List, Dict
import statistics
import json as jsonLib


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
                       startPowerMW=0, log=False, debug=False):
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
            if isOldFile and os.path.getsize(lf) > 50000:
                self.logFile.truncate(0)

        self.debugFile = None
        if debug:
            lf =  f"{name}.debug.txt"
            isOldFile =  os.path.exists(lf)
            self.debugFile = open(lf,"at", buffering=1)
            if isOldFile and os.path.getsize(lf) > 50000:
                self.debugFile.truncate(0)


        warn(f"Batterie monitor created for {name} triggering at {triggerPowerMW/1000:.2f}")

    def evaluate(self):
        if len(self.reads) >= self.statsPoolSize and len(self.reads) > 0:
            self.reads.pop(0)
        power = self._execGetContent("getswitchpower")
        if self.logFile and self.status == self.CHARGING:
            print(f"{self.name}\t{time.time() - self.startTime:.0f}\t{power}",file=self.logFile)
        if self.debugFile and (self.status != Charger.NOT_CHARGING or power >= 10):
            print(
                f"{self.name}\t{datetime.now().time().strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\t{power}\t{self.status}",
                file=self.debugFile)

        if self.status != self.CHARGING:
            # remove values below 10 mW so that when new charging starts
            # the low values of disconnected charge do not average out new values
            self.reads = list(filter(lambda v: v > 10, self.reads))
        self.reads.append(power)

        pMedian = statistics.median(self.reads)

        if len(self.reads) < self.statsPoolSize:
            if pMedian < 170:
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
            if self.debugFile:
                print(
                    f"Switched OFF: {self.name}\t{datetime.now().time().strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\t{power}\t{self.status}",
                    file=self.debugFile)
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
        self.name = "AutoCharger"

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

    WAITING = 2

    def __init__(self, name:str, AIN:str, fritzCon:Any, triggerPowerDiffMW:int, statsPoolSize:int = 3,
                       startPowerMW=260, startTimes:List[Dict[str,datetime]] = [],log=False, debug=False):
        super().__init__(name, AIN, fritzCon, triggerPowerDiffMW, statsPoolSize, startPowerMW, log, debug)
        self.startTimes = startTimes

    def evaluate(self):

        power = self._execGetContent("getswitchpower")

        if self.debugFile and (self.status != Charger.NOT_CHARGING or power >= 10):
            print(f"{self.name}\t{datetime.now().time().strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\t{power}\t{self.status}",file=self.debugFile)

        # if we are in WAITING state check if we are now in a starting time period
        # and switch to CHARGING
        if self.status == self.WAITING:
            self.status = self.evaluateWaiting(power)
            if self.status == self.WAITING:
                return self.status

        if len(self.reads) >= self.statsPoolSize and len(self.reads) > 0:
            self.reads.pop(0)

        if self.logFile and power > 50:
            print(f"{self.name}\t{datetime.now().time().strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\t{power}",file=self.logFile)

        self.reads = list(filter(lambda v: v > 150, self.reads))
        self.reads.append(power)

        pMedian = statistics.median(self.reads)

        if pMedian < 170:
            self.status = self.NOT_CHARGING
            return self.status

        if self.status != self.CHARGING:
            self.startTime = time.time()

            # check if we are outside an allowed start time period
            inWindow = self.inLoadTimeWindow()
            if not inWindow:
                self.status = self.WAITING
                self._execGetContent("setswitchoff")
                if self.debugFile:
                    print(
                        f"Switched OFF: {self.name}\t{datetime.now().time().strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\t{power}\t{self.status}",
                        file=self.debugFile)
                return self.status

            self.status = self.CHARGING

        if len(self.reads) < self.statsPoolSize:
            return self.status

        # switch off if power threshold is reached
        pMax = max(self.reads)
        lowest30 = statistics.quantiles(self.reads, n=10)[2]
        if (pMax - lowest30 > self.triggerPowerMW   # max power in pool has dropped by triggerPower
           or pMax < 10000):                        # this is an accidental on switch by user
            self._execGetContent("setswitchoff")
            if self.debugFile:
                print(
                    f"Switched OFF: {self.name}\t{datetime.now().time().strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\t{power}\t{self.status}",
                    file=self.debugFile)
            print(f"Charged: {self.name}\t{datetime.now().time().strftime('%H:%M')}\t{self.reads}",file=self.logFile)
            self.reads = []

            self.status = self.CHARGED
        return self.status

    def inLoadTimeWindow(self):
        inWindow = False if len(self.startTimes) > 0 else True
        now = datetime.now().time()
        for p in self.startTimes:
            # print(f'now:{now.strftime("%d.%m.%Y %H:%M")} start:{p["start"].strftime("%d.%m.%Y %H:%M")} now:{p["end"].strftime("%d.%m.%Y %H:%M")} ')
            if (p["start"] < p["end"] and now >= p["start"] and now <= p["end"]) \
                    or (p["start"] > p["end"] and (now >= p["start"] or now <= p["end"])):
                inWindow = True
                break
        return inWindow

    def evaluateWaiting(self, power:float)-> int:
        """
        Evaluate poser in state == WAITING
        returns: new status
        """
        if power > 1000:
            return self.CHARGING  ## user switched power back on a second time lets continue charging
        else:
            now = datetime.now().time()
            for p in self.startTimes:
                ## check if we are in the loading time window
                if (    p["start"] < p["end"] and now > p["start"] and now < p["end"]) \
                    or (p["start"] > p["end"] and (now > p["start"] or now < p["end"])):
                    # we were waiting so now we entered the start charging time window, lets do it.
                    self._execGetContent("setswitchon")
                    if self.debugFile:
                        print(
                            f"Switched ON: {self.name}\t{datetime.now().time().strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\t{power}\t{self.status}",
                            file=self.debugFile)
                    return self.CHARGING  ## let the UnuCharger decide if we are charging based on power

            if self.logFile:
                now = datetime.now().time()
                if now.minute % 5 == 0:
                    print(f"{self.name}\t{now.strftime('%H:%M')}\t{time.time() - self.startTime:.0f}\tWAITING",
                          file=self.logFile)
            return self.WAITING


def createCharger(fc:FritzConnection, json:Dict[str,Any])->Charger:
    AIN = json["AIN"]
    name = json["name"]
    statsPoolSize = json["statsPoolSize"]
    startPower = int(json.get("startPowerW","0") * 1000)
    log = json.get("log",False)
    debug = json.get("debug",False)

    if json.get("type", None) == "UNU":
        triggerPowerDiffMW = int(json["triggerPowerDiffW"] * 1000)
        startTimes:List[Dict[str:Any]] = json.get("startTimes", [])
        for p in startTimes:
            p["start"] = datetime.strptime(p["start"],"%H:%M").time()
            p["end"] = datetime.strptime(p["end"], "%H:%M").time()
        return UnuCharger(name, AIN, fc, triggerPowerDiffMW, statsPoolSize, startPower, startTimes, log, debug)
    else:
        triggerPowerMW = int(json["triggerPowerW"] * 1000)
        return Charger(name, AIN, fc, triggerPowerMW, statsPoolSize, startPower, log, debug)


def createAutoCharger(fc:FritzConnection, json:Dict[str,Any]):
    AIN = json["AIN"]
    statsPoolSize =  json["statsPoolSize"]
    chrgrs = []
    for c in json["Charger"]:
        c["AIN"] = AIN
        chrgrs.append(createCharger(fc, c))

    return AutoCharger(chrgrs, statsPoolSize)


class ChargerLoop():
    def __init__(self, setFile):
        with open(setFile) as sFile:
            self.settings = jsonLib.load(sFile)
        self.fritzIP = self.settings["fritzIP"]
        self.user = self.settings["user"]
        self.passWD = self.settings["passWD"]
        self.freq = self.settings["frequencyS"]

        self.fc = FritzConnection(address=self.fritzIP, user=self.user, password=self.passWD,
                                  use_cache=True)
        self.batMonitors: List[Any] = []
        for json in self.settings["Charger"]:
            if "Charger" not in json:
                self.batMonitors.append(createCharger(self.fc, json))
            else:
                self.batMonitors.append(createAutoCharger(self.fc, json))


    def loop(self):
        """
            Loop over known chargers and evalute their state then repeat
        """
        while True:
            for bl in self.batMonitors:
                bl.evaluate()
            time.sleep(self.freq)


def endlessLoop():
    setFile = "settings.json"
    if len(sys.argv) > 1:
        setFile = sys.argv[1]

    while True:
        try:
            chargeLoop = ChargerLoop(setFile)
            chargeLoop.loop()
        except Exception as error:
            time.sleep(30)
            traceback.print_exc()
            warn("Retrying")


#######################################################
if __name__ == "__main__":
    endlessLoop()

