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

while True:

    if iviny:
        iviny.write(ord("1"))
        data=iviny.read()
        print data
#        print "".join([chr(x) for x in data if x != 255])

        iviny.write(ord("H"))
        iviny.write(ord("A"))

    time.sleep(0.01)
