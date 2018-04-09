#!/usr/bin/env python

import datetime
import os
import time

import numpy

from . import consts


def get_log_files(log_directory):
    fns = []
    for fn in os.listdir(log_directory):
        if '.csv' not in fn:
            continue
        if '_' not in fn:
            continue
        fn = os.path.join(log_directory, fn)
        if '_touch' not in fn:
            fns.append(fn)
    fns.sort()
    return fns


def dc(v):
    v = v.decode('utf-8')
    if v in 'LR':
        return 'LR'.index(v)
    if v in 'ub':
        return 'ub'.index(v)
    if v in 'fr':
        return 'fr'.index(v)
    try:
        return int(v)
    except:
        return int('0x' + v, 16)
    return v


def load_log(log_filename):
    # 0: time
    # 1: board
    # 2: event type
    # 3: data0
    # 4: data1
    vs = numpy.loadtxt(
        log_filename, delimiter=',', converters={3: dc, 4: dc}, dtype='int64')
    return vs


def make_time_conversion(fevs):
    fn_to_time = lambda fn: time.mktime(datetime.datetime.strptime(
        os.path.splitext(os.path.basename(fn))[0],
        '%y%m%d_%H%M%S').timetuple())
    # use datetime.datetime.fromtimestamp to convert to datetime
    vs = []
    for fn in sorted(fevs):
        dt = fn_to_time(fn)
        ms = fevs[fn][consts.TIME_COLUMN]
        vs.append((dt, ms))
    a = numpy.array(vs)
    slope, intercept = numpy.polyfit(a[:, 1], a[:, 0], 1)
    event_to_unix_time = lambda t: t * slope + intercept
    return event_to_unix_time


def load_log_directory(log_directory, convert_times=True):
    fns = get_log_files(log_directory)
    fns = [fn for fn in fns if os.path.getsize(fn) != 0]
    d = []
    first_events = {}
    for fn in fns:
        sd = load_log(fn)
        d.append(sd)
        first_events[fn] = sd[0]
    d = numpy.vstack(d)
    # TODO load meta data
    # make time converstion
    if convert_times:
        tc = make_time_conversion(first_events)
        # convert all event times to unix time * 1000
        d[:, 0] = (tc(d[:, 0]) * 1000).astype('int64')
    return numpy.vstack(d)
