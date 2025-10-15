import time
import threading
from flask import Flask

import unuCharger
import traceback
import sys

def warn(strg:str):
    print(strg, file=sys.stderr)


app = Flask(__name__)

@app.route('/')
def UCWeb():
    global chargeLoop

    ret = ""
    for c in chargeLoop.batMonitors:
        ret += f"{c.name}</br>\n"
        if hasattr(c, "chargers"):
            for sc in c.chargers:
                ret += f"&nbsp;&nbsp;{sc.name}</br>\n"

    return ret + 'Hello world2'


chargeLoop:unuCharger.ChargerLoop

def endlessCharge(setFile):
    global chargeLoop
    while True:
        try:
            chargeLoop = unuCharger.ChargerLoop(setFile)
            chargeLoop.loop()
        except Exception as error:
            time.sleep(30)
            traceback.print_exc()
            warn("Retrying")


if __name__ == '__main__':
    # start unuCharger in Background

    setFile = "settings.json"

    thread = threading.Thread(target=endlessCharge, args=(setFile,))
    thread.daemon = True
    thread.start()


    app.run(debug=True, host='0.0.0.0')
