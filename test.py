#!/usr/bin/python
# -*- coding: utf-8 -*-   
#
#  test
#  
#
#  Created by TVA on 11/17/18.
#  Copyright (c) 2018 GitHub. All rights reserved.
#
from AppKit import NSApplication, NSApp
from Foundation import NSObject, NSLog
from Cocoa import NSEvent, NSKeyDownMask
from PyObjCTools import AppHelper


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, handler)


def handler(event):
    try:
        NSLog(u"%@", event)
        print "event:%s" % event
    except KeyboardInterrupt:
        AppHelper.stopEventLoop()


def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    NSApp().setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == '__main__':
    main()
