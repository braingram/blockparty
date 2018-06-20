#!/usr/bin/env python


def teensy_dt(t0, t1):
    """t0 should always be laster than t1, except when the clock rolled over"""
    if t0 < t1:  # rollover
        t0 += 2 ** 32
    return t0 - t1


class Clock(object):
    """synchronize 2 clocks: system and teensy time"""
    def __init__(self):
        pass 