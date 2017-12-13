#!/usr/bin/env python

import os

import numpy

from . import touch


def get_log_files(log_directory):
    fns, tfns = [], []
    for fn in os.listdir(log_directory):
        if '.csv' not in fn:
            continue
        fn = os.path.join(log_directory, fn)
        if '_touch' in fn:
            tfns.append(fn)
        else:
            fns.append(fn)
    fns.sort()
    tfns.sort()
    return fns, tfns


def dc(v):
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


def load_log_directory(log_directory, and_touch=True, binarize_touch=True):
    fns, tfns = get_log_files(log_directory)
    fns = [fn for fn in fns if os.path.getsize(fn) != 0]
    tfns = [tfn for tfn in tfns if os.path.getsize(tfn) != 0]
    d = numpy.vstack([load_log(fn) for fn in fns])
    if and_touch:
        td = numpy.vstack([load_log(fn) for fn in tfns])
        if binarize_touch:
            td, _ = touch.binarize(td)
        d = numpy.vstack((d, td))
        d = d[numpy.argsort(d[:, 0])]
    return d
