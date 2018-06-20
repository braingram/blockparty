#!/usr/bin/env python

from . import animal
from . import cage
from . import clock
from . import event
from . import tube

from .. import consts
from .. import utils

class Colony(object):
    def __init__(self, n_tubes, ring=False, rfid_merge_threshold=None):
        self.ring = ring
        self.tubes = [tube.Tube(i) for i in range(n_tubes)]
        # if ring, n_cages = n_tubes
        # if not ring, n_cages = n_tubes +1
        self.cages = [cage.Cage(i) for i in range(n_tubes + int(self.ring))]
        self.animals = {}  # by rfid
        self.rfid_merge_threshold = rfid_merge_threshold
    
    def parse_event(self, event):
        # event [time, board, type, d0, d1]
        # if rfid read, pass to animal
        if event.etype == consts.EVENT_RFID:
            rfid = event.data0
            if rfid not in self.animals:
                self.animals[rfid] = animal.Animal(rfid)
            animal = self.animals[rfid]
            
            # check if animal is in a different tube or if
            # this read is > merge time later than the last read
            if animal.last_read is None:
                animal.last_read = event
            else:
                last_read = animal.last_read
                if (event.board != last_read.board):
                    # animal seen in different board/tube
                    # TODO check if rfid_merge_threshold should be updated
                    pass
                elif (
                        clock.teensy_dt(event.timestamp, last_read.timestamp)
                        > self.rfid_merge_threshold):
                    # animal read in same tube, but these are separate read
                    # events > merge threshold apart
                    pass
        
        # if beam break, pass to tube
        # if animals read timed out (exceeded rfid_merge_threshold)
        pass
 
    def update(self, line=None, timestamp=None):
        pass