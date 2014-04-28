#!/usr/bin/python
#	IViny - IViny PC Scope
#	Copyright (C) 2014  Caner Durmusoglu <cnr437@gmail.com>
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not, see <http://www.gnu.org/licenses/>.

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Ivmech Mechatronics Innovation Ltd.
# ----------------------------------
# Caner Durmusoglu
# cnr437@gmail.com
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import os
import sys
import pygtk
pygtk.require('2.0')
import gtk
import gobject
import time
import random
import ConfigParser
import numpy as np

from scipy.interpolate import interp1d
from datetime import datetime

DEBUG = False


def get_amd():
    import ctypes
    i = ctypes.c_int()
    kernel32 = ctypes.windll.kernel32
    process = kernel32.GetCurrentProcess()
    kernel32.IsWow64Process(process, ctypes.byref(i))
    is64bit = (i.value != 0)
    return is64bit

CNAME = "iviny"
INFNAME = "IVinyUSB.inf"

PLATFORM = sys.platform
if PLATFORM != "linux2":
    ARCH = get_amd()
    PATH = os.path.join(os.getcwd(), "pyapp")
else:
    PATH = os.getcwd()

IMAGES = os.path.join(PATH, "images")
LIBPATH = os.path.join(PATH, "lib")
CONF = os.path.join(PATH, "IViny.conf")
if not os.path.isfile(CONF):
    c = open(CONF, "w")
    c.write("[%s]\n" % CNAME)
    c.close()

sys.path.append(LIBPATH)

USERPATH = os.path.join(os.path.expanduser("~"), CNAME)
if not os.path.isdir(USERPATH):
    os.mkdir(USERPATH)

import xlsxwriter
from usbdevice import IVinyUSBDevice

NAME = "Iviny Scope"
WIDTH = 800
HEIGHT = 600

red = (0.8, 0.0, 0.0, 1.0)
green = (0.0, 0.8, 0.0, 1.0)
blue = (0.0, 0.0, 0.8, 1.0)
black = (0.0, 0.0, 0.0, 1.0)
white = (1.0, 1.0, 1.0, 1.0)
gray = (0.0, 0.0, 0.0, 0.3)

RESOLUTION = 10     # ADC Cozunurlugu
VOLTAGE = 5.0       # 0V-5V araligi
SCALE = 1.0         # 0V-1V donusumu

RANGES = ["MILIVOLTAGE", "VOLTAGE", "ADC VALUE"]
CURVES = ["LINEAR", "CUBIC", "QUADRATIC"]

BUTTON_SIZE = (130, 30)

DEFAULT_SETTINGS = {"peak_threshold": "0.2",
                    "curve_algorithm": "cubic",
                    "max_seconds": "0",
                    "y_axis": "milivoltage",
                    "max_minutes": "1",
                    "max_hours": "0",
                    "refresh_rate": "40",
                    "last_directory": USERPATH,
                    }
LABEL_RUN = "RUN"
LABEL_STOP = "STOP"
ANALOG_DIGITAL = False

class IViny:

    RUN_COLOR = "lightgreen"
    STOP_COLOR = "lightpink"

    def __init__(self):

        self.data = [[], []]
        self.last_data = self.data
        self.time = []

        self.analogs = []
        self.digitals = []

        self.data_error = 0

        # Ayar dosyasi
        self.config = ConfigParser.RawConfigParser()
        self.config.read(CONF)
        try:
            self.curve_algorithm = self.config.get(CNAME, "curve_algorithm")
            self.refresh_rate = int(self.config.get(CNAME, "refresh_rate"))
            self.last_directory = self.config.get(CNAME, "last_directory")
        except:
            self.default_settings()

        self.run_state = 0
        self.elapsed_time = 0
        self.remain_time = ""
        self.start_time = None
        self.load_last = False
        self.left_arrow = False
        self.right_arrow = False

        self.x = 0
        self.y = 0
        self.step = 50          # X eksenindeki hiz
        self.a_width = WIDTH    # Pencere genisligi
        self.a_height = HEIGHT  # Pencere yuksekligi
        self.offset = 50        # Cevre ofseti
        self.h_offset = 10      # Y eksenindeki ofset
        self.h_gridres = 5      # Y eksenindeki grid
        self.v_gridres = 50     # X eksenindeki grid
        self.h_grids = list(range(0, int(VOLTAGE * 10), self.h_gridres))

        self.sldx = 0
        self.posx = 0
        self.posy = 0

        self.filename = ""

        # Ana pencerenin olusturulmasi, isimlendirilmesi ve boyutlandirilmasi
        self.mainwindow = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.mainwindow.set_position(gtk.WIN_POS_CENTER)
        self.mainwindow.set_title(NAME)
        self.mainwindow.set_size_request(WIDTH, HEIGHT)
        self.mainwindow.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        self.mainwindow.set_icon_from_file(os.path.join(IMAGES, "icon.png"))
        self.mainwindow.set_resizable(False)

        # Tablarin olusuturlmasi
        self.notebook = gtk.Notebook()

        self.gpio_vbox = gtk.VBox()

        vs = gtk.VSeparator
        hs = gtk.HSeparator

        analog_hbox = gtk.HBox()
        self.gpio_vbox.pack_start(analog_hbox)
        self.gpio_vbox.pack_start(hs(), False, False, 0)
        for a in range(2):
            analog = Analog(a)
            self.analogs.append(analog)
            analog_hbox.pack_start(analog, True, True, 10)
            analog_hbox.pack_start(vs(), False, False, 0)

        digital_hbox = gtk.HBox()
        self.gpio_vbox.pack_start(digital_hbox)
        self.gpio_vbox.pack_start(hs(), False, False, 0)
        for d in range(2):
            digital = Digital(d)
            self.digitals.append(digital)
            digital_hbox.pack_start(digital, True, True, 10)
            digital_hbox.pack_start(vs(), False, False, 0)

        self.graph_button = gtk.Button("SHOW GRAPH")

        self.gpio_vbox.pack_start(self.graph_button, True, True, 20)

        self.graph_vbox = gtk.VBox()
        self.settings_vbox = gtk.VBox()

        # Cairo icin cizim alaninin olusturulmasi
        self.fixed = gtk.Fixed()
        self.area = gtk.DrawingArea()
        self.fixed.put(self.area, self.offset, self.offset / 2)
        self.graph_vbox.pack_start(self.fixed)

        # Calistir butonu ve renklerinin olusturulmasi
        self.run_button = gtk.ToggleButton(LABEL_RUN)
        self.run_button.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.color_parse(self.STOP_COLOR))
        self.run_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.RUN_COLOR))
        self.run_button.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(self.RUN_COLOR))

        self.graph_hbox = gtk.HBox()
        self.check_save = gtk.CheckButton("Save File")
        self.limit_time = gtk.CheckButton("Limit Time")
        self.clear_button = gtk.Button("CLEAR")
        self.clear_button.set_size_request(*BUTTON_SIZE)
        self.graph_hbox.pack_start(self.check_save, False, False, 50)
        self.graph_hbox.pack_start(gtk.VSeparator(), False, False)
        self.graph_hbox.pack_start(self.limit_time, False, False, 20)
        self.graph_hbox.pack_end(self.clear_button, False, False, 50)
        self.graph_hbox.pack_end(self.run_button, True, True, 0)

        # Araniyor simgesinin platforma gore gosterilmesi
        if PLATFORM == "linux2":
            self.spinner = gtk.Spinner()
        else:
            self.spinner = gtk.Image()
            self.spinner.set_from_file(os.path.join(IMAGES, "loading.gif"))
        self.graph_hbox.pack_start(self.spinner)

        self.graph_vbox.pack_start(self.graph_hbox)

        self.browse_hbox = gtk.HBox()
        self.browse_hbox.pack_start(gtk.Label("Output Save File: "), False, False, 10)
        self.browse_entry = gtk.Entry()
        self.browse_entry.set_editable(False)

        self.browse_hbox.pack_start(self.browse_entry, True, True, 10)
        self.browse_button = gtk.Button("Browse")
        self.browse_button.set_size_request(*BUTTON_SIZE)
        self.browse_hbox.pack_start(self.browse_button, False, False, 10)

        self.settings_vbox.pack_start(self.browse_hbox, False, False, 10)

        self.max_save_hbox = gtk.HBox()
        self.max_save_hbox.pack_start(gtk.Label("Max Save Time:    "), False, False, 10)
        self.hour_adj = gtk.Adjustment(0, 0, 60, 1, 10, 0)
        self.hourspin = gtk.SpinButton(self.hour_adj)
        self.hourspin.set_value(int(self.config.get(CNAME, "max_hours")))
        self.max_save_hbox.pack_start(self.hourspin, False, True, 10)
        self.max_save_hbox.pack_start(gtk.Label("Hours"), False, False, 0)
        self.max_save_hbox.pack_start(gtk.VSeparator(), False, False, 10)
        self.minute_adj = gtk.Adjustment(1, 0, 60, 1, 10, 0)
        self.minutespin = gtk.SpinButton(self.minute_adj)
        self.minutespin.set_value(int(self.config.get(CNAME, "max_minutes")))
        self.max_save_hbox.pack_start(self.minutespin, False, True, 10)
        self.max_save_hbox.pack_start(gtk.Label("Minutes"), False, False, 0)
        self.max_save_hbox.pack_start(gtk.VSeparator(), False, False, 10)
        self.second_adj = gtk.Adjustment(0, 0, 60, 1, 10, 0)
        self.secondspin = gtk.SpinButton(self.second_adj)
        self.secondspin.set_value(int(self.config.get(CNAME, "max_seconds")))
        self.max_save_hbox.pack_start(self.secondspin, False, True, 10)
        self.max_save_hbox.pack_start(gtk.Label("Seconds"), False, False, 0)

        self.set_limit_time()   # limit saniyelerini koyar.
        self.settings_vbox.pack_start(self.max_save_hbox, False, False, 10)

        self.range_hbox = gtk.HBox()
        self.range_hbox.pack_start(gtk.Label("Unit: "), False, False, 10)
        self.range_combo = gtk.combo_box_new_text()
        for r in RANGES:
            self.range_combo.append_text(r)
        self.range_combo.set_active(RANGES.index(self.config.get(CNAME, "y_axis").upper()))
        self.range_hbox.pack_start(self.range_combo, False, False, 10)

        self.settings_vbox.pack_start(self.range_hbox, False, False, 10)

        #self.peak_threspin = gtk.SpinButton()
        #self.peak_adj = gtk.Adjustment(0, 0, 1.0, 0.1, 0.2, 0)
        #self.peak_threspin = gtk.SpinButton(self.peak_adj)
        #self.peak_threspin.set_digits(2)
        #self.peak_threspin.set_value(float(self.config.get(CNAME, "peak_threshold")))
        #self.range_hbox.pack_start(gtk.VSeparator(), False, False, 10)
        #self.range_hbox.pack_start(gtk.Label("Peak Threshold: "), False, False, 10)
        #self.range_hbox.pack_start(self.peak_threspin, False, False, 10)
        #self.peak_label = gtk.Label(self.config.get(CNAME, "y_axis").capitalize())
        #self.range_hbox.pack_start(self.peak_label, False, False, 0)

        self.curve_hbox = gtk.HBox()
        self.curve_hbox.pack_start(gtk.Label("Curve Algorithm: "), False, False, 10)
        self.curve_combo = gtk.combo_box_new_text()
        for r in CURVES:
            self.curve_combo.append_text(r)
        self.curve_combo.set_active(CURVES.index(self.curve_algorithm.upper()))

        self.curve_refreshspin = gtk.SpinButton()
        self.curve_refresh_adj = gtk.Adjustment(0, 10, 100, 5, 10, 0)
        self.curve_refreshspin = gtk.SpinButton(self.curve_refresh_adj)
        self.curve_refreshspin.set_value(self.refresh_rate)
        self.curve_hbox.pack_start(self.curve_combo, False, False, 10)
        self.curve_hbox.pack_start(gtk.Label("Refresh Rate: "), False, False, 10)
        self.curve_hbox.pack_start(self.curve_refreshspin, False, False, 10)
        self.curve_hbox.pack_start(gtk.Label("Miliseconds"), False, False, 0)

        self.settings_vbox.pack_start(self.curve_hbox, False, False, 10)

        if PLATFORM != "linux2":
            self.driver_hbox = gtk.HBox()
            self.install_button = gtk.Button("Install Driver")
            self.uninstall_button = gtk.Button("Uninstall Driver")
            self.driver_hbox.pack_start(self.install_button, True, True, 50)
            self.driver_hbox.pack_start(self.uninstall_button, True, True, 50)

        self.apply_button = gtk.Button("Apply Settings")
        self.apply_button.set_size_request(*BUTTON_SIZE)
        self.settings_vbox.pack_end(self.apply_button, False, False, 10)
        self.settings_vbox.pack_end(gtk.HSeparator(), False, False, 10)

        if hasattr(self, "driver_hbox"):
            self.settings_vbox.pack_end(self.driver_hbox, False, False, 10)

        self.load_vbox = gtk.VBox()
        self.load_hbox = gtk.HBox()
        self.load_browse_button = gtk.Button("Load File")
        self.load_browse_button.set_size_request(*BUTTON_SIZE)
        self.load_last_button = gtk.Button("Load Last")
        self.load_last_button.set_size_request(*BUTTON_SIZE)
        self.save_last_button = gtk.Button("Save As")
        self.save_last_button.set_size_request(*BUTTON_SIZE)
        self.save_excel_button = gtk.Button("Save EXCEL")
        self.save_excel_button.set_size_request(*BUTTON_SIZE)
        self.load_hbox.pack_start(self.load_browse_button, True, True, 50)
        self.load_hbox.pack_start(self.load_last_button, False, False, 10)
        self.load_hbox.pack_start(self.save_last_button, False, False, 10)
        self.load_hbox.pack_start(self.save_excel_button, False, False, 50)

        self.load_fixed = gtk.Fixed()
        self.load_area = gtk.DrawingArea()
        self.load_fixed.put(self.load_area, self.offset, self.offset / 2)
        self.load_vbox.pack_start(self.load_fixed)
        self.load_vbox.pack_start(self.load_hbox)

        self.notebook.append_page(self.gpio_vbox, gtk.Label("Input / Output"))
        self.notebook.append_page(self.graph_vbox, gtk.Label("Graph View"))
        self.notebook.append_page(self.load_vbox, gtk.Label("Load Data"))
        self.notebook.append_page(self.settings_vbox, gtk.Label("Settings"))

        self.mainwindow.add(self.notebook)
        self.mainwindow.show_all()

        self.resize()
        self.signals()

        # IViny baglantisinin saglanmasi (Threading Yapilacak)
        self.iviny = None

        self.spinner.hide()
        if not DEBUG:
            self.run_button.hide()

        # Threading'ler, self.check threading'i IViny'e baglanabilir
        gobject.timeout_add(70, self.update)
        gobject.timeout_add(30, self.update_value)
        if not DEBUG:
            gobject.timeout_add(500, self.check)

    def signals(self):
    # Sinyallerin olusturulmasi
        self.mainwindow.connect("delete-event", self.destroy)
        self.mainwindow.connect("size-allocate", self.resize)
        self.area.connect("expose-event", self.redraw)
        self.run_button.connect("toggled", self.run_toggled)
        self.clear_button.connect("clicked", self.clear_clicked)
        self.check_save.connect("toggled", self.check_save_toggled)
        self.browse_button.connect("clicked", self.browse_clicked)
        if hasattr(self, "driver_hbox"):
            self.install_button.connect("clicked", self.install_clicked)
            self.uninstall_button.connect("clicked", self.uninstall_clicked)
        self.graph_button.connect("clicked", self.graph_button_clicked)
        self.apply_button.connect("clicked", self.apply_clicked)
        self.range_combo.connect("changed", self.range_changed)
        self.notebook.connect("switch-page", self.notebook_changed)
        self.load_browse_button.connect("clicked", self.load_browse_clicked)
        self.load_last_button.connect("clicked", self.load_last_clicked)
        self.save_last_button.connect("clicked", self.browse_clicked)
        self.save_excel_button.connect("clicked", self.excel_clicked)
        self.load_area.connect("expose-event", self.load_redraw)
        self.load_area.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON1_MOTION_MASK)
        self.load_area.connect("motion_notify_event", self.load_area_motion)
        self.load_area.connect("button-press-event", self.load_area_pressed)
        self.load_area.connect("button-release-event", self.load_area_released)

    def destroy(self, widget=None, data=None):
    # Pencerenin kapatilmasi
        md = gtk.MessageDialog(self.mainwindow,
        gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION,
        gtk.BUTTONS_YES_NO, "Are you sure want to leave?")
        md.set_default_response(gtk.RESPONSE_NO)
        response = md.run()
        if response == gtk.RESPONSE_YES:
            gtk.main_quit()
        else:
            md.destroy()
            return True
        md.destroy()

    def main(self):
    # Ana fonksiyon
        gtk.main()

    def default_settings(self):
        for key, value in list(DEFAULT_SETTINGS.items()):
            self.config.set(CNAME, key, value)

       #Ayar dosyasinin cagirilmasi (ilk kez "with" komutunu kullandigim yer :)
        with open(CONF, 'wb') as cfile:
            self.config.write(cfile)
            cfile.close()
    # Threading fonksiyonu (IViny baglanabilir)

    def check(self):
        self.check_remain_time()
        self.set_sensitives()
        try:
            if not self.iviny:
                self.iviny = IVinyUSBDevice(idVendor=0x16c0, idProduct=0x05df)
                self.iviny_check()
                # IViny BAGLI ise yapilacaklar
                #print "BAGLI"
                if PLATFORM == "linux2":
                    self.spinner.stop()
                self.spinner.hide()
                self.run_button.show()

                self.gpio_vbox.set_sensitive(True)
                if ANALOG_DIGITAL:
                    for ad in self.analogs + self.digitals:
                        ad.set_iviny(self.iviny)
                else:
                    for d in self.digitals:
                        d.set_iviny(self.iviny)
            else:
                if self.data_error > 20:
                    self.iviny_check()

        except:
            # IViny BAGLI DEGIL ise yapilacaklar
            #print "BAGLI DEGIL"
            if PLATFORM == "linux2":
                self.spinner.start()
            self.spinner.show()
            self.run_button.hide()
            self.gpio_vbox.set_sensitive(False)

        #if self.iviny:
        #    return False
        #print "checked"
        return True

    def iviny_check(self):
        try:
            self.iviny.write(ord("1"))
            #self.iviny.write(ord("\n"))
            self.iviny.read()
        except:
            self.iviny = None

    def run_toggled(self, widget=None, event=None):
    #Calistir butonu basilmasi
        try:
            self.iviny.read()
        except:
            pass
        if self.run_state:
            self.run_state = 0
            label = LABEL_RUN
            widget.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(self.RUN_COLOR))
            if self.check_save.get_active() and self.filename:
                self.save_data_file()
            self.start_time = None
        else:
            widget.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(self.STOP_COLOR))
            label = LABEL_STOP
            if self.check_save.get_active():
                if self.filename:
                    if os.path.getsize(self.filename) != 0:
                        response = self.dialog_file_rename()
                        if response == gtk.RESPONSE_OK:
                            self.run_state = 1
                            self.start_time = time.time()
                        else:
                            self.clear_clicked()
                            self.browse_clicked()
                            self.run_state = 1
                            self.start_time = time.time()
                            #self.run_state = 0
                            #label = LABEL_RUN
                            #self.start_time = None
                            #widget.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse("lightgreen"))
                    else:
                        self.run_state = 1
                        self.start_time = time.time()
                else:
                    self.run_state = 1
                    self.check_save.set_active(False)
            else:
                self.run_state = 1
                self.start_time = time.time()
        widget.set_label(label)

    def graph_button_clicked(self, widget=None, event=None):
        self.notebook.set_current_page(1)

    def clear_clicked(self, widget=None, event=None):
        if not self.run_state:
            self.filename = 0
            self.data = [[], []]
            self.last_data = self.data
            self.time = []
            self.elapsed_time = 0
            self.start_time = None
            self.load_last = False
            self.set_analog_sensitive(True)

    def check_save_toggled(self, widget=None, event=None):
        if widget.get_active() and not self.filename:
            self.browse_entry.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("lightyellow"))
            self.notebook.set_current_page(3)
        else:
            self.browse_entry.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

    def browse_clicked(self, widget=None, event=None):
    #Kaydetmek icin dosya gosterilmesi
        filename = None
        ext = ".ivs"
        file_chooser = gtk.FileChooserDialog(title="Save Scope File", action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog_filter = gtk.FileFilter()
        dialog_filter.set_name("IViny Scope File")
        dialog_filter.add_pattern("*" + ext)
        file_chooser.add_filter(dialog_filter)

        date = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        file_chooser.set_current_name("SCOPE_" + date + ext)
        if not os.path.isdir(self.last_directory):
            self.last_directory = USERPATH
        file_chooser.set_current_folder(self.last_directory)

        response = file_chooser.run()

        if response == gtk.RESPONSE_OK:
            filename = file_chooser.get_filename()
            if not os.path.splitext(filename)[1]:
                filename += ext
        elif response == gtk.RESPONSE_CANCEL:
            filename = None
        file_chooser.destroy()

        if filename:
            self.browse_entry.set_text(filename)
            self.filename = filename
            self.last_directory = os.path.split(filename)[0]
            self.browse_entry.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
            self.save_data_file()
            self.set_last_directory()

    def load_browse_clicked(self, widget=None, event=None):
    #Kayitli dosya acilmasi
        filename = None
        ext = ".ivs"
        file_chooser = gtk.FileChooserDialog(title="Select a File", action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        dialog_filter = gtk.FileFilter()
        dialog_filter.set_name("IViny Scope File")
        dialog_filter.add_pattern("*" + ext)
        file_chooser.add_filter(dialog_filter)
        if not os.path.isdir(self.last_directory):
            self.last_directory = USERPATH
        file_chooser.set_current_folder(self.last_directory)

        response = file_chooser.run()

        if response == gtk.RESPONSE_OK:
            filename = file_chooser.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            filename = None
        file_chooser.destroy()

        if filename:
            data = open(filename)
            self.filename = filename
            self.last_directory = os.path.split(filename)[0]
            lines = data.readlines()
            self.time = [float(x.strip().split(",")[0]) for x in lines]
            for ch in range(len(self.data)):
                temp_data = [x.strip().split(",")[ch + 1] for x in lines]
                self.last_data[ch] = [float(x) for x in temp_data if not x == "C"]

            if len(self.last_data[0]) > 7:
                self.load_last = True
                self.sldx = 0
                if len(self.last_data[0] * self.step) > self.a_width:
                    self.right_arrow = True
            data.close()
            self.set_last_directory()
        else:
            self.load_last = False

    def excel_clicked(self, widget=None, event=None):
    # Excel kaydetmek icin dosya gosterilmesi
        filename = None
        ext = ".xlsx"
        file_chooser = gtk.FileChooserDialog(title="Save Excel File", action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog_filter = gtk.FileFilter()
        dialog_filter.set_name("Excel File")
        dialog_filter.add_pattern("*" + ext)
        file_chooser.add_filter(dialog_filter)

        response = file_chooser.run()

        if response == gtk.RESPONSE_OK:
            filename = file_chooser.get_filename()
            if not os.path.splitext(filename)[1]:
                filename += ext
        elif response == gtk.RESPONSE_CANCEL:
            filename = None
        file_chooser.destroy()

        if filename and self.load_last:
            self.excel_sheet(filename)
            for i, data in enumerate(self.last_data[0]):
                if self.range_combo.get_active() == 0:
                    value = data / SCALE * 1000
                elif self.range_combo.get_active() == 1:
                    value = data / SCALE
#                elif self.range_combo.get_active() == 2:
#                    value = data / SCALE * 100

                self.ws.write(self.xls_x, 0, float(value))
                self.ws.write(self.xls_x, 1, round(float(self.time[i]), 4))
                self.xls_x += 1
            self.excel_chart()
            self.wb.close()

    def load_last_clicked(self, widget=None, event=None):
        for ch in range(len(self.data)):
            self.last_data[ch] = self.data[ch]
            if len(self.last_data[ch]) > 7:
                self.load_last = True
                self.sldx = 0
                if len(self.last_data[ch] * self.step) > self.a_width:
                    self.right_arrow = True
            else:
                self.load_last = False

    def save_data_file(self):
        if self.filename:
            savefile = open(self.filename, "w")
            write = list(zip(self.time, *self.data))
            savefile.writelines(["%.7f,%s,%s\n" % item for item in write])
            savefile.close()

    def range_changed(self, widget=None, event=None):
    #Eksen biriminin degistirilmesi
        pass
        #self.peak_label.set_text(RANGES[widget.get_active()].lower().capitalize())

    def install_clicked(self, widget=None, event=None, opt="install"):
        oldcwd = os.getcwd()
        DRIVER = os.path.join(oldcwd, "DRIVER")
        os.chdir(DRIVER)
        if ARCH:
            bit = 64
        else:
            bit = 86
        installer = "installer_x%d.exe" % bit
        if os.path.isfile(installer) and os.path.isfile(INFNAME):
            cmd = "%s %s --inf=%s" % (installer, opt, INFNAME)
            os.popen(cmd)
        os.chdir(oldcwd)

    def uninstall_clicked(self, widget=None, event=None):
        self.install_clicked(opt="uninstall")

    def apply_clicked(self, widget=None, event=None):
    #Ayarlarin onay butonu
        self.curve_algorithm = CURVES[self.curve_combo.get_active()].lower()

        self.config.set(CNAME, "max_hours", int(self.hourspin.get_value()))
        self.config.set(CNAME, "max_minutes", int(self.minutespin.get_value()))
        self.config.set(CNAME, "max_seconds", int(self.secondspin.get_value()))
        self.config.set(CNAME, "y_axis", RANGES[self.range_combo.get_active()].lower())
        self.config.set(CNAME, "peak_threshold", self.peak_threspin.get_value())
        self.config.set(CNAME, "curve_algorithm", self.curve_algorithm)

        self.set_limit_time()
        #Ayar dosyasinin cagirilmasi (ilk kez "with" komutunu kullandigim yer :)
        with open(CONF, 'wb') as cfile:
            self.config.write(cfile)
            cfile.close()

    def notebook_changed(self, widget=None, event=None, data=None):
    #Tablarin degistirlmesi
        return
        #print widget.get_current_page(), data
        #self.load_last = False
        old_page = widget.get_current_page()
        md = gtk.MessageDialog(self.mainwindow,
        gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION,
        gtk.BUTTONS_OK_CANCEL, "Are you sure to leave graph?")
        response = md.run()
        md.destroy()
        if response == gtk.RESPONSE_CANCEL:
            pass
        elif response == gtk.RESPONSE_OK:
            widget.set_current_page(data)

    def load_area_motion(self, widget=None, event=None):
        self.posx = event.x
        self.posy = event.y
        mx, my = self.posx - self.old_posx, self.posy - self.old_posy
        self.sldx -= int(mx / self.step)
        if self.sldx < 0:
            self.sldx = 0
            self.left_arrow = False
        elif self.sldx > len(self.last_data[0]) - self.a_width / self.step / 2:
            self.sldx = len(self.last_data[0]) - self.a_width / self.step / 2
            self.right_arrow = False
        else:
            self.left_arrow = True
            self.right_arrow = True

    def load_area_pressed(self, widget=None, event=None):
        self.old_posx = event.x
        self.old_posy = event.y

    def load_area_released(self, widget=None, event=None):
        pass
        #print abs(self.posx - self.old_posx), abs(self.posy - self.old_posy)

    def set_limit_time(self):
        hours = int(self.hourspin.get_value())
        minutes = int(self.minutespin.get_value())
        seconds = int(self.secondspin.get_value())
        self.limit_seconds = hours * 3600 + minutes * 60 + seconds

    def set_last_directory(self):
        self.config.set(CNAME, "last_directory", self.last_directory)
        with open(CONF, 'wb') as cfile:
            self.config.write(cfile)
            cfile.close()

    def set_analog_sensitive(self, state):
        for i, a in enumerate(self.analogs):
            a.get_widget().state_button.set_sensitive(state)

    def set_sensitives(self):
        if self.run_state:
            state = False
            self.set_analog_sensitive(state)
        else:
            state = True

        self.notebook.get_nth_page(2).set_sensitive(state)
        self.notebook.get_nth_page(3).set_sensitive(state)
        self.check_save.set_sensitive(state)
        self.limit_time.set_sensitive(state)
        self.clear_button.set_sensitive(state)

    def check_remain_time(self):
        remain = int(self.limit_seconds - self.elapsed_time)
        if self.run_state:
            if self.limit_time.get_active() and remain <= 0:
                self.run_button.set_active(False)
        minutes, seconds = divmod(remain, 60)
        hours, minutes = divmod(minutes, 60)
        self.remain_time = " [ %.2d:%.2d:%.2d ] " % (hours, minutes, seconds)

        label = LABEL_STOP
        remain_time = " "
        if self.run_state and self.limit_time.get_active():
            remain_time += self.remain_time
            label += remain_time
            self.run_button.set_label(label)

    def update_value(self):
        self.get_value()
        return True

    def update(self):
    # Threading fonksiyonu (Gorsel Arayuz)
        #if self.iviny:
        self.mainwindow.queue_draw()
        return True

    def resize(self, widget=None, event=None):
    # Pencerenin yeniden boyutlandirilmasi
        self.width = self.a_width + self.offset * 2
        self.height = self.a_height + self.offset * 2
        self.mainwindow.set_size_request(self.width, self.height)
        self.width, self.height = self.mainwindow.get_size()
        self.area.set_size_request(self.a_width, self.a_height)
        self.load_area.set_size_request(self.a_width, self.a_height)

    def redraw(self, widget, event):
    # Pencerenin icerigindeki CAIRO nesnelerini tekrar cizilmesi
        self.area.window.clear()
        self.cairo = self.area.window.cairo_create()
        self.draw()

    def load_redraw(self, widget, event):
    # Pencerenin icerigindeki CAIRO nesnelerini tekrar cizilmesi
        self.load_area.window.clear()
        self.cairo = self.load_area.window.cairo_create()
        self.load_draw()

    def draw(self):
    # Herseyin cizilmesi
        self.draw_frame()
        self.draw_grid()
        self.draw_graph_slide()

    def load_draw(self):
    # Herseyin cizilmesi
        self.draw_frame()
        self.draw_grid()
        self.draw_arrows()
        if self.load_last:
            self.draw_load_graph()

    def draw_frame(self):
    # Cerceve olusuturlmasi
        c = self.cairo
        c.set_source_rgba(*white)
        c.paint()
        c.move_to(0, 0)
        c.line_to(self.a_width, 0)
        c.line_to(self.a_width, self.a_height)
        c.line_to(0, self.a_height)
        c.line_to(0, 0)
        c.set_source_rgba(*black)
        c.stroke()

    def draw_grid(self):
    # Gridlerin olusturulmasi
        c = self.cairo
        gridstep = (self.a_height - (self.h_offset * 2)) / len(self.h_grids)
        for h in self.h_grids:
            c.move_to(0, self.h_offset + gridstep * h / self.h_gridres)
            c.line_to(self.a_width, self.h_offset + gridstep * h / self.h_gridres)
            self.draw_axes(0, h)
        self.draw_axes(0, h + self.h_gridres)
        c.move_to(0, self.a_height - self.h_offset)
        c.line_to(self.a_width, self.a_height - self.h_offset)
        for v in range(0, self.a_width, self.v_gridres):
            c.move_to(v, 0)
            c.line_to(v, self.a_height)

        dash = [1.0, 1.0]
        c.set_dash(dash)
        c.set_source_rgba(*black)
        c.stroke()

    def draw_axes(self, x, y):
    # Eksen yazilarinin olusturulmasi
        c = self.cairo
        gridstep = (self.a_height - (self.h_offset * 2)) / len(self.h_grids)
        c.select_font_face("Sans")
        c.set_font_size(16.0)
        c.set_source_rgba(*black)
        #print self.h_grids
        #c.move_to(x, self.a_height - y*15.5)
        c.move_to(x, self.a_height - y * gridstep / self.h_gridres)
        if self.range_combo.get_active() == 0:
            value = str(y / SCALE * 100) + "mV"
        elif self.range_combo.get_active() == 1:
            value = str(y / (SCALE * 10.0)) + "V"
#        elif self.range_combo.get_active() == 2:
#            value = str(y * 2) + "%"
        c.show_text(value)

    def draw_time(self):
        c = self.cairo
        c.select_font_face("Sans")
        c.set_font_size(12.0)
        c.set_source_rgba(*black)
        newtime = self.time[self.sldx:self.sldx + self.a_width / self.step / 2 ]

        for i, s in enumerate(newtime):
            if i:
                c.move_to(i * self.v_gridres, self.a_height - self.h_offset)
                c.show_text(str(round(s, 2)) + "s")

    def draw_arrows(self):
        c = self.cairo
        dash = [1.0, 0.0]
        c.set_dash(dash)
        c.set_source_rgba(*gray)

        if self.right_arrow:
            c.move_to(self.a_width, self.a_height / 2)
            c.line_to(self.a_width - self.v_gridres, self.a_height / 2 + self.v_gridres)
            c.line_to(self.a_width - self.v_gridres, self.a_height / 2 - self.v_gridres)
            c.line_to(self.a_width, self.a_height / 2)

            c.fill()

        if self.left_arrow:
            c.move_to(0, self.a_height / 2)
            c.line_to(self.v_gridres, self.a_height / 2 + self.v_gridres)
            c.line_to(self.v_gridres, self.a_height / 2 - self.v_gridres)
            c.line_to(0, self.a_height / 2)

            c.fill()

    def draw_graph_slide(self):
    # Kayan grafik olusuturlmasi
        for ch, a in enumerate(self.analogs):
            if a.get_state():
                c = self.cairo
                xmax = len(self.data[ch]) if len(self.data[ch]) > self.a_width / self.step else self.a_width / self.step
                xmin = self.a_width / self.step - xmax

                newdata = [int(x * (self.a_height / VOLTAGE)) * SCALE + self.h_offset if x < (2 ** RESOLUTION) else self.a_height - self.h_offset * 2 for x in self.data[ch][xmin * (-1):]]
                ln = len(newdata)
                if ln > 7:
                    x = np.linspace(0, ln, ln)
                    y = np.asarray(newdata)
                    f = interp1d(x, y, kind=self.curve_algorithm)
                    xnew = np.linspace(0, ln, ln * self.step)
                    nd = f(xnew).tolist()
                else:
                    nd = newdata
                for y in nd:
                    c.move_to(self.x + xmin * (-1), self.a_height - self.h_offset - self.y)
                    self.x = self.x + 1        # self.step
                    self.y = y
                    c.line_to(self.x + xmin * (-1), self.a_height - self.h_offset - self.y)
                self.x = xmin
                dash = [1.0, 0.0]
                c.set_dash(dash)
                color = self.analogs[ch].get_line_color()
                c.set_source_rgb(*color)
                c.stroke()

    def get_value(self):
    # Analog ceviricinin cozunurlugundeki degerleri pixel'e cevirilmesi
        if self.iviny:
            if self.run_state:
                try:
                    self.iviny.write(ord("1"))
                    data = self.iviny.read()

                    data = "".join([chr(x) for x in data if x != 255])
                    #print data
                    if data:
                        if ";" in data:
                            analogs, digitals = data.split(";")
                        else:
                            analogs = data
                        if "," in analogs:

                            analogvalues = [int(a) for a in analogs.split(",") if int(a) < 2 ** RESOLUTION]

                            for i, a in enumerate(self.analogs):
                                if a.get_state():
                                    self.data[i].append(analogvalues[i] * VOLTAGE / (2 ** RESOLUTION))
                                else:
                                    self.data[i].append("C")
                            self.elapsed_time = time.time() - self.start_time
                            self.time.append(self.elapsed_time)
                    self.data_error = 0
                except:
                    #self.get_value()
                    self.data_error += 1
                    pass

            else:
                try:
                    self.iviny.write(ord("1"))
                    #self.iviny.write(ord("\n"))
                    data = self.iviny.read()

                    data = "".join([chr(x) for x in data if x != 255])
                    if data:
                        if ";" in data:
                            analogs, digitals = data.split(";")
                            if "," in digitals:
                                digitals = [int(a) for a in digitals.split(",") if int(a) < 2]

                                for i, d in enumerate(self.digitals):
                                    d.set_state(digitals[i])

                        else:
                            digitals = None
                except:
                    #self.get_value()
                    pass

        # DEBUG olayi
        elif DEBUG and self.run_state:
            self.elapsed_time = time.time() - self.start_time
            self.time.append(self.elapsed_time)
            self.data[0].append(random.choice(range(300, 400)))

    def draw_load_graph(self):
    # Duran grafik olusuturlmasi
        def peaks(data, step):
            n = len(data) - len(data) % step
            slices = [data[i:n:step] for i in range(step)]
            peak_max = reduce(np.maximum, slices)
            peak_min = reduce(np.minimum, slices)
            return np.transpose(np.array([peak_max, peak_min]))

        for ch in range(len(self.last_data)):
            if len(self.last_data[ch]):
                c = self.cairo
                newdata = [int(x * (self.a_height / VOLTAGE)) * SCALE + self.h_offset if x < (2 ** RESOLUTION) else self.a_height - self.h_offset * 2 for x in self.last_data[ch][self.sldx:self.sldx + self.a_width / self.step / 2]]
                ln = len(newdata)
                x = np.linspace(0, ln, ln)
                y = np.asarray(newdata)
                algorithm = CURVES[self.curve_combo.get_active()].lower()
                f = interp1d(x, y, kind=self.curve_algorithm)
                xnew = np.linspace(0, ln, ln * self.step * 2)
                nd = f(xnew).tolist()
                x = 0
                for y in nd:
                    c.move_to(x, self.a_height - self.h_offset - y)
                    x += 1
                    c.line_to(x, self.a_height - self.h_offset - y)

                #self.sldx += self.step     # Kayan
                dash = [1.0, 0.0]
                c.set_dash(dash)
                color = self.analogs[ch].get_line_color()
                c.set_source_rgba(*color)
                c.set_line_width(5)
                c.stroke()

            self.draw_time()

    def excel_sheet(self, filename):
    # Excel uzerinde verilen isimde sheet olusturulmasi
        self.wb = xlsxwriter.Workbook(filename)
        self.ws = self.wb.add_worksheet(NAME)
        self.xls_x = 0
        self.xls_y = 0

    def excel_chart(self):
    # Excel uzerinde grafik olusturulmasi
        chart = self.wb.add_chart({'type': 'line'})
        chart.add_series(
        {
        'categories': '=%s!$B$1:$B$%d' % (NAME, self.xls_x + 1),            # X ekseni uzerindeki zaman degerleri
        'values': '=%s!$A$1:$A$%d' % (NAME, self.xls_x + 1),                # Y ekseni uzerindeki akim degerleri
        'smooth': True,
        'line': {'width': 1.5},
        })
        chart.set_title({'name': NAME})
        chart.set_x_axis({'name': 'TIME (s)'})
        if self.range_combo.get_active() == 0:
            chart.set_y_axis({'name': 'MILIVOLTAGE (mV)', 'min': 0, 'max': VOLTAGE * 1000 / SCALE})
        elif self.range_combo.get_active() == 1:
            chart.set_y_axis({'name': 'VOLTAGE (V)', 'min': 0, 'max': VOLTAGE / SCALE})
#        elif self.range_combo.get_active() == 2:
#            chart.set_y_axis({'name': 'ABSORBANCE (%)', 'min': 0, 'max': 100})
        chart.set_size({'width': 800, 'height': 600})
        self.ws.insert_chart('D1', chart)

    def dialog_file_rename(self):
        qd = gtk.MessageDialog(self.mainwindow,
        gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION,
        gtk.BUTTONS_OK_CANCEL, "There exists scope file already. Do you want to overwrite on it?")
        response = qd.run()
        qd.destroy()
        return response

ANALOG_BUTTON_SIZE = (30, 50)


class Analog(gtk.VBox):

    # TODO
    # Milivolt, ADC, Volt secenegi
    # Scale secenegi (0-1v, 0-5v vs.)
    # Grafik renk secenegi

    ON_COLOR = "#90EE90"        # lightgreen
    OFF_COLOR = "#FFB6C1"       # lightpink

    COLORS = ["#FFB6C1",    # lightpink
        "#EE82EE",          # violet

        "#90EE90",          # lightgreen
        "#2E8B57",          # seagreen

        "#ADD8E6",          # lightblue
        "#48D1CC",          # mediumturquoise

        "#4169E1",          # royalblue
        "#7B68EE",          # mediumslateblue

        "#FF6347",          # tomato
        "#DC143C",          # crimson

        "#D2691E",          # chocolate
        "#8B4513",          # saddlebrown
        ]
    def __init__(self, CHANNEL=0):

        super(Analog, self).__init__()

        self.mode_value = 1
        self.value = 0
        self.state_value = 1
        self.channel_no = CHANNEL
        self.name_label = gtk.Label("Channel %d" % self.channel_no)
        self.color_buttons = []

        if ANALOG_DIGITAL:
            self.mode_button = gtk.ToggleButton("ANALOG")
            self.digital = Digital(self.channel_no + 2, False)

        self.state_button = gtk.ToggleButton("ON")

        self.state_button.set_size_request(*ANALOG_BUTTON_SIZE)
        self.value_label = gtk.Label(self.value)

        self.maxvolt_adj = gtk.Adjustment(0, 0, 10, 1, 0.1, 0)
        self.scale_spin = gtk.SpinButton(self.maxvolt_adj)
        self.scale_spin.set_digits(1)
        self.scale_spin.set_value(5.0)
        self.color_button = gtk.Button()
        self.color_button.set_size_request(*BUTTON_SIZE)
        self.color = self.COLORS[9 + self.channel_no]
        self.new_color = ""
        self.old_colorbox = gtk.EventBox()
        self.new_colorbox = gtk.EventBox()

        #self.range_combo = gtk.combo_box_new_text()
        #for r in RANGES:
        #    self.range_combo.append_text(r)
        #self.range_combo.set_active(0)

        self.analog_box = gtk.VBox()

        self.color_button_changed()

        self.state_button.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.color_parse(self.OFF_COLOR))
        self.state_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.ON_COLOR))
        self.state_button.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(self.ON_COLOR))

        self.pack_start(self.name_label, False, False, 10)
        if ANALOG_DIGITAL:
            self.pack_start(self.mode_button, False, False, 10)
        self.pack_start(self.analog_box, False, False, 10)
        self.analog_box.pack_start(self.state_button, False, False, 10)

        self.setting_hbox = gtk.HBox()

        self.setting_hbox.pack_start(gtk.Label("Volt"), False, False, 5)
        self.setting_hbox.pack_start(self.scale_spin, True, True, 5)
        self.setting_hbox.pack_start(gtk.Label("Color"), False, False, 5)
        self.setting_hbox.pack_start(self.color_button, True, True, 5)

        self.analog_box.pack_start(self.setting_hbox, False, False, 10)

        self.analog_box.pack_start(self.value_label, False, False, 5)

        self.signals()

    def signals(self):
        self.state_button.connect("toggled", self.state_changed)
        if ANALOG_DIGITAL:
            self.mode_button.connect("toggled", self.mode_changed)
        self.color_button.connect("clicked", self.color_clicked)

    def state_changed(self, widget=None, event=None):
        if self.state_value:
            self.state_value = 0
            color = self.OFF_COLOR
            state = "OFF"
        else:
            self.state_value = 1
            color = self.ON_COLOR
            state = "ON"

        widget.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(color))
        widget.set_label(state)

    def mode_changed(self, widget=None, event=None):
        if self.mode_value:
            self.mode_value = 0
            color = self.OFF_COLOR
            state = "DIGITAL"
            self.analog_box.hide()
            if not self.digital in self.children():
                self.pack_start(self.digital, False, False, 10)
            self.digital.show_all()
            #self.digital.direction_button.clicked()
            #self.digital.direction_button.clicked()
        else:
            self.mode_value = 1
            color = self.ON_COLOR
            state = "ANALOG"
            self.digital.hide()
            self.analog_box.show()

        #widget.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(color))
        widget.set_label(state)

    def get_widget(self):
        return self

    def get_state(self):
        return self.state_value

    def set_value(self, value):
        self.value = value

    def set_iviny(self, IVINY):
        self.digital.set_iviny(IVINY)

    def color_clicked(self, widget=None, event=None):
        # Renk dialogu
        color_dialog = gtk.Dialog("Chose Color", None,
                        gtk.DIALOG_MODAL,
                        (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                        gtk.STOCK_APPLY, gtk.RESPONSE_ACCEPT))

        row = 6
        column = 2

        table = gtk.Table(row, column, True)
        for i in range(row):
            for j in range(column):
                name = self.COLORS[j + column * i]
                color_button = gtk.ToggleButton()
                color_button.set_size_request(100, 50)
                color_button.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.color_parse(name))
                color_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(name))
                color_button.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(name))
                color_button.connect("toggled", self.color_toggled)
                self.color_buttons.append(color_button)
                table.attach(color_button, j, j + 1, i, i + 1)

        table.set_col_spacings(10)
        table.set_row_spacings(10)

        color_dialog.vbox.pack_start(table, False, False, 10)
        color_dialog.vbox.pack_start(gtk.HSeparator(), False, False, 0)
        self.old_colorbox.add(gtk.Label("OLD"))
        self.new_colorbox.add(gtk.Label("NEW"))
        color_dialog.vbox.pack_start(self.old_colorbox, False, False, 0)
        color_dialog.vbox.pack_start(self.new_colorbox, False, False, 0)
        self.old_colorbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.color))
        self.new_colorbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.color))

        color_dialog.vbox.show_all()

        color_dialog.set_default_response(gtk.RESPONSE_REJECT)
        response = color_dialog.run()
        if response == gtk.RESPONSE_ACCEPT:
            if self.new_color:
                self.color = self.new_color
                self.color_button_changed()
            self.color_buttons = []
        else:
            color_dialog.destroy()
            self.color_buttons = []
            return True
        color_dialog.destroy()

    def color_toggled(self, widget=None, event=None):
        if widget.get_active():
            for i, button in enumerate(self.color_buttons):
                if button != widget:
                    button.set_active(False)
                else:
                    button.set_active(True)
                    color = self.COLORS[i]
                    self.new_color = color
            self.new_colorbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(color))

    def color_button_changed(self):
        self.color_button.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.color_parse(self.color))
        self.color_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.color))
        self.color_button.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(self.color))

        #for i, button in enumerate(self.color_buttons):
            #if button == widget:
                #print self.COLORS[i]

    def get_line_color(self):
        hex_color = str(gtk.gdk.color_parse(self.color))
        #return red[:3] # Son hata icin bypass
        return tuple(map(lambda s: int(s, 16)/255.0,
                     (hex_color[1:3], hex_color[3:5], hex_color[5:7])))

DIGITAL_BUTTON_SIZE = (30, 50)


class Digital(gtk.VBox):

    OUT_COLOR = "#ADD8E6"        # lightblue
    IN_COLOR = "#90EE90"         # lightgreen
    LOW_COLOR = "#FFB6C1"        # lightpink
    HIGH_COLOR = "#90EE90"       # lightgreen

    def __init__(self, PORT=0, LABEL=True):

        super(Digital, self).__init__()

        self.direction = 1
        self.port_no = PORT
        self.state_value = 0
        self.first = True
        if LABEL:
            self.name_label = gtk.Label("Digital %d" % self.port_no)
        self.direction_button = gtk.ToggleButton("INPUT")
        self.direction_button.set_size_request(*DIGITAL_BUTTON_SIZE)
        self.state_button = gtk.ToggleButton("LOW")
        self.state_button.set_size_request(*DIGITAL_BUTTON_SIZE)
        self.state_labelbox = gtk.EventBox()
        self.state_label = gtk.Label()
        self.state_labelbox.add(self.state_label)

        self.direction_button.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.color_parse(self.OUT_COLOR))
        self.direction_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.IN_COLOR))
        self.direction_button.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(self.IN_COLOR))

        self.state_button.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.color_parse(self.HIGH_COLOR))
        self.state_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.LOW_COLOR))
        self.state_button.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(self.LOW_COLOR))

        if LABEL:
            self.pack_start(self.name_label, False, False, 10)
        self.pack_start(self.direction_button, False, False, 10)
        self.pack_start(self.state_labelbox, True, True, 15)

        self.signals()

    def signals(self):
        self.direction_button.connect("toggled", self.direction_changed)
        self.state_button.connect("toggled", self.state_changed)

    def direction_changed(self, widget=None, event=None):
        if self.first:
            self.pack_start(self.state_button, True, True, 0)
            self.first = False

        if self.direction:
            self.direction = 0
            direction = "OUTPUT"
            color = self.OUT_COLOR
            self.set_direction(True)
            self.state_labelbox.hide()
            self.state_button.show()
        else:
            self.direction = 1
            direction = "INPUT"
            color = self.IN_COLOR
            self.set_direction(False)
            self.state_button.hide()
            self.state_button.set_active(False)
            self.state_labelbox.show()

        widget.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(color))
        widget.set_label(direction)

    def state_changed(self, widget=None, event=None):
        if self.state_value:
            self.state_value = 0
            self.set_output(False)
            state = "LOW"
            color = self.LOW_COLOR
        else:
            self.state_value = 1
            self.set_output(True)
            state = "HIGH"
            color = self.HIGH_COLOR

        widget.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse(color))
        widget.set_label(state)

    def set_state(self, state):
        if state:
            self.state_value = 1
            state_text = "HIGH"
            color = self.HIGH_COLOR
        else:
            self.state_value = 0
            state_text = "LOW"
            color = self.LOW_COLOR
        self.state_labelbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(color))
        self.state_label.set_markup("<big><big><big>" + state_text + "</big></big></big>")

    def set_iviny(self, IVINY):
        self.iviny = IVINY

    def set_output(self, state):
        self.iviny.write(ord("1"))
        if state:
            self.iviny.write(ord("H"))
        else:
            self.iviny.write(ord("L"))
        self.iviny.write(ord("A") + self.port_no)

        try:
            self.iviny.read()
        except:
            pass

    def set_direction(self, direction):
        self.iviny.write(ord("1"))
        if direction:
            self.iviny.write(ord("O"))
        else:
            self.iviny.write(ord("I"))
        self.iviny.write(ord("A") + self.port_no)
        try:
            self.iviny.read()
        except:
            pass


def set_proc_name(newname):
    # Linux icin sistem isminin verilmesi
    if sys.platform != "linux2":
        return
    from ctypes import cdll, byref, create_string_buffer
    libc = cdll.LoadLibrary('libc.so.6')
    buff = create_string_buffer(len(newname) + 1)
    buff.value = newname
    libc.prctl(15, byref(buff), 0, 0, 0)

if __name__ == "__main__":
    set_proc_name(NAME)
    app = IViny()
    app.main()