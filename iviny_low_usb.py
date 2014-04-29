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

time_list = []
data_list = []
start_time = time.time()
elapsed_time = 0

while elapsed_time < 2:
    if iviny:
        iviny.write(ord("1"))
        raw_data=iviny.read()
        #print raw_data

        data = "".join([chr(x) for x in raw_data if x != 255])
        #print data
        elapsed_time = time.time() - start_time
        time_list.append(elapsed_time)
        analogs = data.split(";")[0]
        analog1 = analogs.split(",")[0]
        data_list.append(analog1)

    time.sleep(0.000001)

savefile = open(os.path.join(PATH, "test.ivs"), "w")
write = list(zip(time_list, data_list))
savefile.writelines(["%.7f,%s\n" % item for item in write])
savefile.close()