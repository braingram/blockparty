#!/usr/bin/env python

import os

import numpy


def get_log_files(log_directory):
    fns = []
    for fn in os.listdir(log_directory):
        if '.csv' not in fn:
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


def load_log_directory(log_directory):
    fns = get_log_files(log_directory)
    fns = [fn for fn in fns if os.path.getsize(fn) != 0]
    d = numpy.vstack([load_log(fn) for fn in fns])
    return d
