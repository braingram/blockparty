#!/usr/bin/env python

import numpy

from . import consts
from . import db


def binarize(tdata, max_ratio_threshold=0.4):
    bids = db.all_boards(tdata)
    r = {}
    ts = {}
    # process each board separately
    for bid in bids:
        td = db.sel(tdata, board=bid)
        tl = td[:, consts.TOUCH_LEFT_COLUMN].copy()
        tr = td[:, consts.TOUCH_RIGHT_COLUMN].copy()
        
        # compute thresholds
        tlt = (tl.ptp() * max_ratio_threshold + tl.min())
        trt = (tr.ptp() * max_ratio_threshold + tr.min())
        
        # invert?
        if tlt < tl.mean():
            # invert left
            tl *= -1
            tlt *= -1
        if trt < tr.mean():
            tr *= -1
            trt *= -1
        
        # save thresholds
        ts[bid] = (tlt, trt)
        
        # find all super-threshold events
        tdb = td.copy()
        tdb[:, consts.TOUCH_LEFT_COLUMN] = tl > tlt
        tdb[:, consts.TOUCH_RIGHT_COLUMN] = tr > trt
        
        # find transitions (rising or falling)
        m = numpy.diff(tdb, axis=0)

        # get left/right board events
        le = tdb[1:][numpy.abs(m[:, consts.TOUCH_LEFT_COLUMN]) == 1].copy()
        re = tdb[1:][numpy.abs(m[:, consts.TOUCH_RIGHT_COLUMN]) == 1].copy()
        
        # reorganize to [time, board, type, side, high/low]
        le[:, consts.TOUCH_STATE_COLUMN] = le[:, consts.TOUCH_LEFT_COLUMN]
        re[:, consts.TOUCH_STATE_COLUMN] = re[:, consts.TOUCH_RIGHT_COLUMN]
        le[:, consts.TOUCH_SIDE_COLUMN] = consts.TOUCH_LEFT
        re[:, consts.TOUCH_SIDE_COLUMN] = consts.TOUCH_RIGHT
        
        # recombine events
        r[bid] = numpy.vstack((le, re))
        
        # set event type to touch binary
        r[bid][:, consts.EVENT_COLUMN] = consts.EVENT_TOUCH_BINARY
        
        # sort by time
        #r[bid] = r[bid][numpy.argsort(r[bid][:, 0])]

    # combine events from all boards
    evs = numpy.vstack(r.values())
    
    # sort by time
    evs = evs[numpy.argsort(evs[:, consts.TIME_COLUMN])]
    
    return evs, ts