#!/usr/bin/env python

from . import animal
from . import cage
from . import clock
from . import event
from . import tube

from .. import consts
from .. import utils

class Colony(object):
    def __init__(
            self, n_tubes, ring=False, rfid_merge_threshold=800,
            autotune_merge_threshold=True):
        self.ring = ring
        self.clock = clock.Clock()
        self.tubes = [tube.Tube(i) for i in range(n_tubes)]
        # if ring, n_cages = n_tubes
        # if not ring, n_cages = n_tubes +1
        self.cages = [cage.Cage(i) for i in range(n_tubes + int(self.ring))]
        self.animals = {}  # by rfid
        self.autotune_merge_threshold = autotune_merge_threshold
        self.rfid_merge_threshold = rfid_merge_threshold
    
    def process_event(self, event):
        # event [time, board, type, d0, d1]
        if event.etype == consts.EVENT_SYNC:
            self.clock.sync(event.timestamp)
        event.world_timestamp = self.clock.teensy_to_world(event.timestamp)
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
                    if (
                            (event.board == last_read.board + 1) or
                            (self.ring and (
                                event.board == 0 and
                                last_read.board == len(self.tubes) - 1))):
                        # moved 'right'
                        # between last_read and event, animal was in
                        # cage between tubes event.board and last_read.board
                        cage = event.board

                        # check against previous predictions, if matches
                        # accept all previous predictions
                        animal.set_occupancy(cage, last_read, event)
                        
                        # predicting that animal is now in cage to the right
                        # of event.board
                        if self.ring and event.board == len(self.tubes) - 1:
                            cage = 0
                        else:
                            cage = event.board + 1
                        p = [event.world_timestamp, cage]
                        animal.set_prediction(cage, event)
                    elif (
                            (event.board == last_read.board - 1) or
                            (self.ring and (
                                event.board == len(self.tubes) - 1 and
                                last_read.board == 0))):
                        # moved 'left'
                        # between last_read and event, animal was in
                        # cage between tubes event.board and last_read.board
                        cage = last_event.board
                        
                        # check against previous predictions, if matches
                        # accept all previous predictions
                        animal.set_occupancy(cage, last_read, event)
                        
                        # predicting that animal is now in cage to the right
                        # of event.board
                        cage = event.board
                        animal.set_prediction(cage, event)
                    else:
                        # animal teleported!
                        # TODO count misses
                        # TODO fill in gap?
                        
                        # reject all previous predictions, reset animal position
                        # to unknown
                        animal.clear_predictions(event)
                    if self.autotune_merge_threshold:
                        # check if rfid_merge_threshold should be updated
                        dt = event.world_timestamp - last_read.world_timestamp
                        if dt < self.rfid_merge_threshold:
                            dt = self.rfid_merge_threshold
                elif (
                        event.world_timestamp - last_read.world_timestamp
                        > self.rfid_merge_threshold):
                    # animal read in same tube, but these are separate reads
                    # events > merge threshold apart
                    
                    # predicting that the animal moved out of the adjacent
                    # cage, through this tube to the connected cage
                    cage = animal.get_cage()
                    if cage is not None:
                        # check cage is adjacent to tube, if not, missed read
                        lc = event.board
                        rc = event.board + 1
                        if self.ring and rc > len(self.tubes) - 1:
                            rc = 0
                        if cage == lc:
                            # predict animal moved right
                            animal.set_prediction(rc, event)
                        elif cage == rc:
                            # predict animal moved left
                            animal.set_prediction(lc, event)
                        else:
                            # TODO count misses
                            # TODO fill in gap
                            animal.clear_predictions(event)
                            pass
        
        # if beam break, pass to tube
        # if animals read timed out (exceeded rfid_merge_threshold)
        pass
 
    def parse_event(self, line):
        t, b, et, d0, d1 = line.strip()split(',')
        return event.Event(int(t), int(b), int(et), d0, d1)

    def update(self, line=None, timestamp=None):
        pass