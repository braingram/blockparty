#!/usr/bin/env python

import datetime
import time

import numpy


def teensy_dt(t0, t1):
    """t0 should always be laster than t1, except when the clock rolled over"""
    if t0 < t1:  # rollover
        t0 += 2 ** 32
    return t0 - t1


def world_to_datetime(w):
    return datetime.datetime.fromtimestamp(w / 1000.)


class Clock(object):
    """synchronize 2 clocks: system and teensy time"""
    def __init__(self):
        self.last_teensy_time = None
        #self.last_sync = None
        self.teensy_time_offset = 0
        self._tw_slope = None
        self._tw_intercept = None
    
    def reset_rollover(self):
        self.teensy_time_offset = 0
        self.last_teensy_time = None
    
    def sync(self, matching_times):
        # compute clock slope and offset
        vs = numpy.array(matching_times)
        self._sync_times = vs
        self._tw_slope, self._tw_intercept = numpy.polyfit(
            vs[:, 0], vs[:, 1], 1)
    
    """
    def sync(self, teensy_time, world_time=None):
        if world_time is None:
            world_time = time.time()
        self.last_sync = (teensy_time, world_time)
        self.teensy_time_offset = 0
    """
    
    def teensy_to_world(self, t0):
        if self.last_teensy_time is None:
            self.last_teensy_time = t0
        if t0 < self.last_teensy_time:
            self.teensy_time_offset += 2 ** 32
        self.last_teensy_time = t0
        t0 += self.teensy_time_offset
        if self._tw_slope is None or self._tw_intercept is None:
            # if not synced, return millis time
            return t0
        return t0 * self._tw_slope + self._tw_intercept
        """
        if self.last_sync is None:
            self.sync(t0)
        if self.last_teensy_time is None:
            self.last_teensy_time = t0
        if t0 < self.last_teensy_time:
            self.teensy_time_offset += 2 ** 32
        w = (
            (t0 + self.teensy_time_offset - self.last_sync[0])
            + self.last_sync[1] * 1000.)
        if as_datetime:
            return world_to_datetime(w)
        return w
        """