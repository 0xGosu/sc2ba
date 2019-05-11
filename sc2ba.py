#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#  sc2ba
#
#
#  Created by TVA on 11/17/18.
#  Copyright (c) 2018 GitHub. All rights reserved.
#
import re

import datetime
import time
from collections import namedtuple

import os
import keyboard
# import objc
import sys

BuildStep = namedtuple('BuildStep', ['supply', 'sync', 'time', 'message'])

lotv_regex = re.compile(r'([+\-\d]+)\|?(\w*)\t\s*(\d+:\d+)\t\s*([\w ,]+)')


def parse_build(build_content, factor=1, verbose=0, max_time=60 * 15):
    build_orders = list()
    for match in lotv_regex.findall(build_content):
        supply = match[0]
        sync_keys = match[1]
        m, s = match[2].split(':')
        btime = datetime.timedelta(minutes=int(m), seconds=int(s)).seconds
        msg = match[3]
        step = BuildStep(supply, sync_keys, btime / factor, msg)
        if verbose:
            print(step)
        if supply[0] == '+':  # repeated step
            duration = int(supply)
            while btime + duration <= max_time:
                btime += duration
                build_orders.append(BuildStep(supply, sync_keys, btime / factor, msg))
        build_orders.append(step)
    build_orders.sort(key=lambda s: s.time)
    return build_orders


def find_build_step(second, build_orders):
    return binary_search_step(second, 0, len(build_orders), build_orders)
    prev_step = None
    for step in build_orders:  # build_orders must be sorted in time
        if second < step.time:
            return prev_step
        prev_step = step
    return step


def binary_search_step(second, b, e, build_orders):
    mid = (b + e) / 2
    step = build_orders[mid]
    if second == step.time:
        return step
    elif second > step.time:
        if mid == b:
            return step
        return binary_search_step(second, mid, e, build_orders)
    else:
        if b == e:
            return None
        return binary_search_step(second, b, mid, build_orders)


def say(msg):
    os.system("say '%s'" % msg)


class Runner(object):
    build_name = ""
    build_orders = []
    cur_second = 0
    offset = 0
    last_step = None
    stop_now = False

    sync_handler_map = {}


def run_build(run, start_key='', max_time=60 * 15):
    keyboard.call_later(say, args=['build %s is ready' % run.build_name], delay=0.1)
    print("build is ready", run.build_name)
    if start_key:
        print("Press {} to start".format(start_key))
        keyboard.wait(start_key)
    runner.stop_now = False
    keyboard.call_later(say, args=['start'], delay=0)
    start_time = datetime.datetime.now()
    cur_second = 0
    last_step = None
    while cur_second <= max_time:
        cur_second = (datetime.datetime.now() - start_time).seconds
        run.cur_second = cur_second
        second = cur_second + run.offset
        step = find_build_step(second, run.build_orders)
        if step != last_step:
            keyboard.call_later(say, args=[step.message], delay=0)
            print(cur_second, run.offset, step)
            last_step = step
            run.last_step = step
        if run.stop_now or step == run.build_orders[-1]:
            # final step
            return
        time.sleep(0.1)
    keyboard.call_later(say, args=['build %s is stop' % run.build_name], delay=0.1)


def process_runner_build_orders(run, enable_sync=True):
    for step in run.build_orders:
        if step.sync and len(step.sync) >= 2 and enable_sync:
            print("create sync for:", step)

            def make_sync_build():
                step_time, keys = step.time, step.sync  # duplicated the value to avoid referrence

                def f(step_time=step_time):
                    print("sync build", run.cur_second, step_time)
                    if run.cur_second > step_time:  # only sync backward (go back in time)
                        run.offset = step_time - run.cur_second  # offset will be negative
                        # remove remove sync listerner
                        handler = run.sync_handler_map.pop(keys, None)
                        if handler:
                            keyboard.remove_word_listener(handler)
                            print("build synced and handler removed")

                return f

            run.sync_handler_map[str(step.sync)] = keyboard.add_word_listener(str(step.sync[:-1]),
                                                                              make_sync_build(),
                                                                              triggers=[str(step.sync[-1])],
                                                                              match_suffix=True,
                                                                              timeout=0.5)


def print_test(kb_event, *args):
    print("%s + %s at %s" % (kb_event.modifiers, kb_event.name, kb_event.time))


def get_build_path(verbose=0):
    build_folder_path = os.path.join(os.getcwd(), 'build')
    build_list = sorted([p for p in os.listdir(build_folder_path) if p.endswith('.txt')])
    build_index = None
    if len(sys.argv) >= 2:
        build_index = (int(sys.argv[1]) - 1) % len(build_list)
        file_path = os.path.join(build_folder_path, build_list[build_index])
    else:
        file_path = 'build/PvZ_DT_Drop_Into_Archon.txt'
    build_name = os.path.split(file_path)[-1].replace('.txt', '')
    if verbose:
        print("Build index: %s, path: %s" % (build_index, file_path))
    return file_path, build_name


def main():
    # print("PyObjC_Version=%s" % objc.__version__)
    # print("PyObjC_BUILD_RELEASE=%s" % objc.PyObjC_BUILD_RELEASE)
    global runner
    runner = Runner()

    file_path, build_name = get_build_path(verbose=1)
    with open(file_path) as f:
        bo = parse_build(f.read(), verbose=0, factor=1)
    # for s in bo:
    #     print s
    runner.build_name = build_name.replace('_', ' ')
    runner.build_orders = bo
    runner.offset = 1

    # enable sync feature
    process_runner_build_orders(runner, enable_sync=True)

    # test code
    # keyboard.hook(print_test, suppress=False)
    # keyboard.wait('command')

    def stop_now(*args):
        runner.stop_now = True
        with open(file_path) as f:
            bo = parse_build(f.read())
            runner.build_orders = bo
            print("stop and reload build")

    keyboard.add_word_listener('stop', stop_now, triggers=['space'], match_suffix=True, timeout=1)
    while 1:
        run_build(runner, start_key='q')


if __name__ == '__main__':
    main()
