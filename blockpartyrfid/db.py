#!/usr/bin/env python

import os
import sys

import numpy

from . import consts
from . import io


if sys.version_info.major > 2:
    unicode = str


def sel(vs, board=None, event=None, data0=None, data1=None, timerange=None):
    if isinstance(event, (str, unicode)):
        event = consts.event_strings[event]
    if isinstance(data0, (str, unicode)):
        data0 = consts.data_strings[event][0][data0]
    if isinstance(data1, (str, unicode)):
        data1 = consts.data_strings[event][1][data1]
    m = numpy.ones(vs.shape[0], dtype='bool')
    if board is not None:
        m &= (vs[:, consts.BOARD_COLUMN] == board)
    if event is not None:
        m &= (vs[:, consts.EVENT_COLUMN] == event)
    if data0 is not None:
        m &= (vs[:, consts.DATA0_COLUMN] == data0)
    if data1 is not None:
        m &= (vs[:, consts.DATA1_COLUMN] == data1)
    if timerange is not None:
        assert len(timerange) == 2
        m &= (vs[:, consts.TIME_COLUMN] < timerange[1])
        m &= (vs[:, consts.TIME_COLUMN] > timerange[0])
    return vs[m]


def remap_ids(evs, rmap):
    # rmap: {old key: new key...}
    for k in rmap:
        evs[
            (evs[:, consts.DATA0_COLUMN] == k) &
            (evs[:, consts.EVENT_COLUMN] == consts.EVENT_RFID),
            consts.DATA0_COLUMN] = rmap[k]


def _reduce_dict(d):
    if isinstance(d, (list, tuple, numpy.ndarray)):
        return d
    if isinstance(d, dict):
        if len(d.keys()) == 1 and list(d.keys())[0] is None:
            return _reduce_dict(d[None])
        else:
            return {k: _reduce_dict(d[k]) for k in d}
    raise TypeError("Cannot reduce type: %s" % type(d))


def split_events(vs, board=True, event=True, data0=True, data1=True):
    svs = {}
    if board:
        bids = all_boards(vs)
    else:
        bids = [None, ]
    if event:
        evs = numpy.unique(vs[:, consts.EVENT_COLUMN])
    else:
        evs = [None, ]
    for bid in bids:
        svs[bid] = {}
        for ev in evs:
            d = sel(vs, board=bid, event=ev)
            if data0:
                d0s = numpy.unique(d[:, consts.DATA0_COLUMN])
            else:
                d0s = [None, ]
            if data1:
                d1s = numpy.unique(d[:, consts.DATA1_COLUMN])
            else:
                d1s = [None, ]
            svs[bid][ev] = {}
            for d0 in d0s:
                svs[bid][ev][d0] = {}
                for d1 in d1s:
                    svs[bid][ev][d0][d1] = sel(d, data0=d0, data1=d1)
    # re-combine
    return _reduce_dict(svs)


def all_boards(vs):
    return numpy.unique(vs[:, consts.BOARD_COLUMN])


def all_animals(vs):
    return numpy.unique(
        sel(vs, event='rfid', data1=0)[:, consts.RFID_ID_COLUMN])


def sum_range(a):
    """ sum ranges [column 0 = start_time, column 1 = end_time]
    without double counting overlaps"""
    s = 0
    if len(a) == 0:
        return s
    for i in range(len(a) - 1):
        if a[i, 1] < a[i, 0]:
            raise Exception(
                "Invalid range, end time is before start[%i]: %s" % (i, a[i]))
        if a[i, 1] > a[i + 1, 0]:
            s += a[i + 1, 0] - a[i, 0]
        else:
            s += a[i, 1] - a[i, 0]
    s += a[-1, 1] - a[-1, 0]
    return s


def by_animal(events):
    aids = all_animals(events)
    return {aid: sel(events, event='rfid', data0=aid) for aid in aids}


def merge_close_reads(reads, threshold=1000):
    # keep cross board reads
    m = numpy.ones(len(reads), dtype='bool')
    m[1:] = numpy.diff(reads[:, 0]) > threshold
    m[1:] |= numpy.diff(reads[:, 1]) != 0
    return reads[m]
