#!/usr/bin/env python


class Event(object):
    def __init__(self, timestamp, board, etype, data0, data1):
        self.timestamp = timestamp
        self.board = board
        self.etype = etype
        self.data0 = data0
        self.data1 = data1
    
    def __repr__(self):
        return (
            "%s<t: %i, B:%i, T:%i, D0:%s, D1:%s>" % (
                self.__class__.__name__,
                self.timestamp,
                self.board, self.etype,
                self.data0, self.data1))