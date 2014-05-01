#!/usr/bin/env python

import os
import sys
import time

PATH = os.getcwd()
LIBPATH = os.path.join(PATH, "lib")
sys.path.append(LIBPATH)
from usbdevice import IVinyUSBDevice

while True:
    try:
        iviny = IVinyUSBDevice(idVendor=0x16c0, idProduct=0x05df)
        break
    except:
        time.sleep(1)

while 1:
    if iviny:
        iviny.write(ord("1"))
        raw_data=iviny.read()

        data = "".join([chr(x) for x in raw_data if x != 255])
        print data

    time.sleep(0.01)
