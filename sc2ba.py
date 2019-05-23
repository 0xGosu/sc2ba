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

lotv_regex = re.compile(r'([+\-\d]+)\|?(\w*\+?)\s*\t?\s*(\d+:\d+)\t\s*([\w +,.]+)')

MAX_BUILD_TIME = 60 * 20
SYNC_DELTA = 2
START_OFFSET = 1
CMD_KEY_TIMEOUT = 1.2
SYNC_KEY_TIMEOUT = 0.9
TIME_SLEEP_UNIT = 0.2
# this should be equal 1 unless for testing
FACTOR = 1


def parse_build(build_content, verbose=0, max_time=MAX_BUILD_TIME):
    build_orders = list()
    for match in lotv_regex.findall(build_content):
        supply = match[0]
        sync_keys = match[1]
        m, s = match[2].split(':')
        btime = datetime.timedelta(minutes=int(m), seconds=int(s)).seconds
        msg = match[3].strip()
        step = BuildStep(supply, sync_keys, btime / FACTOR, msg)
        if verbose:
            print(step)
        if supply[0] == '+':  # repeated step
            duration = int(supply)
            while btime + duration <= max_time:
                btime += duration
                build_orders.append(BuildStep(supply, sync_keys, btime / FACTOR, msg))
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


def say(msg, verbose=False):
    if verbose:
        print("say: " + msg)
    os.system("say '%s'" % msg)


class Runner(object):
    build_path = ""
    build_name = ""
    build_orders = []
    cur_second = 0
    offset = 0
    offset_before_sync = None
    last_step = None
    stop_now = False

    sync_handler_map = {}


def process_step_message(step):
    for message in step.message.split('.'):
        if not message:
            continue
        m = re.search(r'^\+(\d+)\s+(.+)$', message)
        if m:
            delay = int(m.group(1)) / FACTOR
            message = m.group(2)
        else:
            delay = 0
        keyboard.call_later(say, args=[message], delay=delay)


def run_build(run, start_key='', max_time=MAX_BUILD_TIME):
    if start_key:
        print("Press {} to start".format(start_key))
        keyboard.wait(start_key)
    runner.stop_now = False
    keyboard.call_later(say, args=['start'], delay=0)
    start_time = time.time()
    run.cur_second = 0
    run.last_step = None
    second = 0
    while second <= max_time:
        run.cur_second = time.time() - start_time
        second = run.cur_second + run.offset
        step = find_build_step(second, run.build_orders)
        if step != run.last_step:
            process_step_message(step)
            print("%.2f %.2f"%(run.cur_second, run.offset), step)
            run.last_step = step
        if run.stop_now or step == run.build_orders[-1]:
            # final step
            break
        time.sleep(TIME_SLEEP_UNIT)
    keyboard.call_later(say, args=['build is stop', True], delay=0)


def process_runner_build_orders(run, enable_sync=True):
    # remove all sync handler
    if run.sync_handler_map:
        print("remove all existing sync handler")
        for handler_instance in run.sync_handler_map.values():
            try:
                keyboard.remove_word_listener(handler_instance)
            except KeyError:
                pass

    for step in run.build_orders:
        if step.sync and len(step.sync) >= 2 and enable_sync:

            if step.sync[-1] == '+':
                keys = step.sync[:-1]  # remove char + out of keys sync
                _rmv_handler = str(step.sync)
            else:
                keys = step.sync
                _rmv_handler = str(keys) + str(step.time)

            print("create sync %s for:" % (keys), step)

            def make_sync_build():
                def f(step_time=step.time, remove_handler_key=_rmv_handler):
                    print("sync build %.2f <> %d"%(run.cur_second, step_time))
                    # only sync backward (go back in time) and current time if off by more than SYNC_DELTA
                    if run.cur_second > step_time - (START_OFFSET + SYNC_DELTA):
                        if abs(run.cur_second + run.offset - step_time) > SYNC_DELTA:
                            run.offset_before_sync = run.offset
                            run.offset = step_time - run.cur_second  # offset will be negative
                            keyboard.call_later(say, args=['synced'], delay=0)
                        else:
                            keyboard.call_later(say, args=['good'], delay=0)
                        # still removed the handler even though SYNC_DELTA check failed
                        if remove_handler_key is not None:  # remove remove sync listerner
                            handler = run.sync_handler_map.pop(remove_handler_key, None)
                            if handler:
                                try:
                                    keyboard.remove_word_listener(handler)
                                except KeyError:
                                    pass
                        print("build synced and handler removed")

                return f

            run.sync_handler_map[str(keys) + str(step.time)] = keyboard.add_word_listener(str(keys[:-1]),
                                                                                          make_sync_build(),
                                                                                          triggers=[str(keys[-1])],
                                                                                          match_suffix=True,
                                                                                          timeout=SYNC_KEY_TIMEOUT)


def get_build_path(verbose=0):
    build_folder_path = os.path.join(os.getcwd(), 'build')
    build_list = sorted([p for p in os.listdir(build_folder_path) if p.endswith('.txt')])
    build_path_list = [os.path.join(build_folder_path, build_path) for build_path in build_list]
    build_index = None
    if len(sys.argv) >= 2:
        build_index = (int(sys.argv[1]) - 1) % len(build_list)
        file_path = build_path_list[build_index]
    else:
        file_path = build_path_list[-1]  # default is last one 'build/PvZ_DT_Drop_Into_Archon.txt'

    if verbose:
        print("Build index: %s, build path: %s" % (build_index, file_path))
    return file_path, build_path_list


def reload_runner(set_offset=0, verbose='say'):
    global runner
    runner.build_name = os.path.split(runner.build_path)[-1].replace('.txt', '').replace('_', ' ')
    print("Reload build: {}".format(runner.build_name))
    with open(runner.build_path) as f:
        bo = parse_build(f.read())
    runner.build_orders = bo
    if set_offset is not None:
        runner.offset = set_offset

    # enable sync feature
    process_runner_build_orders(runner, enable_sync=True)
    # build is now ready
    if verbose and 'say' in verbose:
        m = re.search(r'say (.+)', verbose)
        if m:
            msg = m.group(1)
        else:
            msg = 'build %s is ready' % runner.build_name
        keyboard.call_later(say, args=[msg], delay=0)


def main():
    # print("PyObjC_Version=%s" % objc.__version__)
    # print("PyObjC_BUILD_RELEASE=%s" % objc.PyObjC_BUILD_RELEASE)
    global runner
    runner = Runner()

    runner.build_path, build_path_list = get_build_path(verbose=0)

    # test code
    # keyboard.hook(print_test, suppress=False)
    # keyboard.wait('command')

    def stop_now():
        runner.stop_now = True
        print("stop build now")

    keyboard.add_word_listener('stop', stop_now, triggers=['space'], match_suffix=True, timeout=CMD_KEY_TIMEOUT)

    for i in range(len(build_path_list)):
        build_index = i + 1

        def make_switch_build_func():
            def f(build_path=str(build_path_list[i]), _build_index=build_index):
                runner.build_path = build_path
                reload_runner(set_offset=None, verbose='say build %d is ready' % (_build_index))

            return f

        keyboard.add_word_listener('b' + str(build_index), make_switch_build_func(), triggers=['space'],
                                   match_suffix=True, timeout=CMD_KEY_TIMEOUT)
    # add reset current build trigger (remove offset and reinstall sync point)
    keyboard.add_word_listener('bs', lambda: reload_runner(verbose='say build is reset'), triggers=['space'],
                               match_suffix=True, timeout=CMD_KEY_TIMEOUT)

    # add go back to offset_before_sync
    def go_back_to_offset_before_sync():
        if runner.offset_before_sync is not None:
            runner.offset = runner.offset_before_sync
            keyboard.call_later(say, args=['redo'], delay=0)

    keyboard.add_word_listener('bb', go_back_to_offset_before_sync, triggers=['space'],
                               match_suffix=True, timeout=CMD_KEY_TIMEOUT)

    while 1:
        reload_runner(set_offset=START_OFFSET)
        run_build(runner, start_key='q')


if __name__ == '__main__':
    main()
