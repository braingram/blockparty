#!/usr/bin/env python

import copy
import datetime
import glob
import os
import time

import numpy

from .animal import Animal, debug_animal
from .cage import Cage
from .clock import Clock
from .event import Event
from .tube import Tube

from .. import consts
#from .. import utils


class Colony(object):
    def __init__(
            self, n_tubes, ring=False, rfid_merge_threshold=800,
            autotune_merge_threshold=False):
        self.ring = ring
        self.clock = Clock()
        self.tubes = [Tube(i) for i in range(n_tubes)]
        # if ring, n_cages = n_tubes
        # if not ring, n_cages = n_tubes +1
        self.cages = [Cage(i) for i in range(n_tubes + int(self.ring))]
        self.animals = {}  # by rfid
        self.autotune_merge_threshold = autotune_merge_threshold
        self.rfid_merge_threshold = rfid_merge_threshold
    
    def process_event(self, event):
        # event [time, board, type, d0, d1]
        #if event.etype == consts.EVENT_SYNC:
        #    self.clock.sync(
        #        event.timestamp, getattr(event, 'worldtimestamp', None))
        event.world_timestamp = self.clock.teensy_to_world(event.timestamp)
        #event.world_timestamp = event.timestamp
        # if rfid read, pass to animal
        if event.etype == consts.EVENT_RFID:
            rfid = event.data0
            if rfid not in self.animals:
                self.animals[rfid] = Animal(rfid)
            animal = self.animals[rfid]
            
            # check if animal is in a different tube or if
            # this read is > merge time later than the last read
            if animal.last_read is None:
                animal.last_read = event
            else:
                if event.data0 == debug_animal:
                    print("Animal read: %s, %s" % (event.timestamp, event.board))
                last_read = animal.last_read
                animal.last_read = event
                if (event.board != last_read.board):
                    # animal seen in different board/tube
                    # track animal reads
                    animal.was_read(event.board, event.world_timestamp)
                    self.tubes[event.board].read_animal(
                            rfid, event.world_timestamp)
                    # track tube reads
                    if (
                            (event.board == last_read.board + 1) or
                            (self.ring and (
                                event.board == 0 and
                                last_read.board == len(self.tubes) - 1))):
                        if event.data0 == debug_animal:
                            print("moved right")
                        # moved 'right'
                        # between last_read and event, animal was in
                        # cage between tubes event.board and last_read.board
                        cage = event.board

                        # check against previous predictions, if matches
                        # accept all previous predictions
                        animal.set_occupancy(cage, last_read, event)
                        #animal.was_read(event.board, event.world_timestamp)
                        #self.tubes[event.board].read_animal(
                        #    rfid, event.world_timestamp)
                        
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
                        if event.data0 == debug_animal:
                            print("moved left")
                        # moved 'left'
                        # between last_read and event, animal was in
                        # cage between tubes event.board and last_read.board
                        cage = last_read.board
                        
                        # check against previous predictions, if matches
                        # accept all previous predictions
                        animal.set_occupancy(cage, last_read, event)
                        #animal.was_read(event.board, event.world_timestamp)
                        #self.tubes[event.board].read_animal(
                        #    rfid, event.world_timestamp)
                        
                        # predicting that animal is now in cage to the right
                        # of event.board
                        cage = event.board
                        animal.set_prediction(cage, event)
                    else:
                        if event.data0 == debug_animal:
                            print("teleported")
                        # animal teleported!
                        # TODO count misses
                        #animal.was_read(event.board, event.world_timestamp)
                        animal.teleported(
                            event.world_timestamp,
                            last_read.board, event.board)
                        #self.tubes[event.board].read_animal(
                        #    rfid, event.world_timestamp)
                        
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
                    # track animal reads
                    animal.was_read(event.board, event.world_timestamp)
                    self.tubes[event.board].read_animal(
                            rfid, event.world_timestamp)
                    
                    # predicting that the animal moved out of the adjacent
                    # cage, through this tube to the connected cage
                    cage = animal.get_predicted_cage()
                    if cage is not None:
                        if event.data0 == debug_animal:
                            print("predicting...")
                        # check cage is adjacent to tube, if not, missed read
                        lc = event.board
                        rc = event.board + 1
                        if self.ring and rc > len(self.tubes) - 1:
                            rc = 0
                        if cage == lc:
                            # predict animal moved right
                            animal.set_prediction(rc, event)
                            #animal.was_read(event.board, event.world_timestamp)
                            #self.tubes[event.board].read_animal(
                            #    rfid, event.world_timestamp)
                        elif cage == rc:
                            # predict animal moved left
                            animal.set_prediction(lc, event)
                            #animal.was_read(event.board, event.world_timestamp)
                            #self.tubes[event.board].read_animal(
                            #    rfid, event.world_timestamp)
                        else:
                            # TODO count misses
                            # TODO fill in gap
                            animal.clear_predictions(event)
                            #animal.was_read(event.board, event.world_timestamp)
                            animal.teleported(
                                event.world_timestamp,
                                last_read.board, event.board)
                            #self.tubes[event.board].read_animal(
                            #    rfid, event.world_timestamp)
                else:
                    if event.data0 == debug_animal:
                        print("skipping(merging)")
        
        # if beam break, pass to tube
        # if animals read timed out (exceeded rfid_merge_threshold)
 
    def parse_event(self, line):
        t, b, et, d0, d1 = line.strip().split(',')
        return Event(int(t), int(b), int(et), d0, d1)

    def update(self, line=None, timestamp=None):
        raise NotImplementedError("online occupancy is not yet working")
    
    def read_events(self, path):
        evs = []
        with open(path, 'r') as f:
            for l in f:
                evs.append(self.parse_event(l))
        return evs
 
    def process_directory(
            self, directory, pre_measure_rfid_merge_threshold=True,
            pre_sync_clocks=True, multi_animal_event_threshold=None):
        fns = glob.glob(os.path.join(directory, '*.csv'))
        # read all events
        evs = {}
        for fn in fns:
            evs[fn] = self.read_events(fn)
        if pre_measure_rfid_merge_threshold or pre_sync_clocks:
            # find min board-to-board time
            ats = {}
            mdt = None
            sts = []
            for fn in fns:
                # parse timestamp from filename
                dts = os.path.splitext(os.path.basename(fn))[0]
                dt = datetime.datetime.strptime(dts, '%y%m%d_%H%M%S')
                # convert to ms
                start_time = time.mktime(dt.timetuple()) * 1000.
                synced = False
                for e in evs[fn]:
                    if e.etype == consts.EVENT_SYNC:
                        if synced:
                            raise Exception(
                                "Found >1 time sync in file: %s" % (fn, ))
                        # handle possible rollover
                        t = self.clock.teensy_to_world(e.timestamp)
                        sts.append([t, start_time])
                        synced = True
                    elif e.etype == consts.EVENT_RFID:
                        aid = e.data0
                        if aid in ats and (ats[aid].board != e.board):
                            dt = e.timestamp - ats[aid].timestamp
                            if dt < 0:
                                # account for rollover
                                dt = e.timestamp - (ats[aid] + 2 ** 32)
                            if mdt is None:
                                mdt = dt
                            else:
                                mdt = min(dt, mdt)
                        ats[aid] = e
            if pre_measure_rfid_merge_threshold:
                self.rfid_merge_threshold = mdt
                if multi_animal_event_threshold is None:
                    multi_animal_event_threshold = mdt
            if pre_sync_clocks:
                self.clock.sync(sts)
            self.clock.reset_rollover()
        
        for t in self.tubes:
            t.multi_animal_event_threshold = (
                multi_animal_event_threshold)
        for fn in fns:
            """
            # parse timestamp from filename
            dts = os.path.splitext(os.path.basename(fn))[0]
            dt = datetime.datetime.strptime(dts, '%y%m%d_%H%M%S')
            start_time = time.mktime(dt.timetuple())
            synced = False
            """
            for e in evs[fn]:
                """
                if e.etype == consts.EVENT_SYNC:
                    if synced:
                        raise Exception(">1 time sync in this file")
                    e.world_timestamp = start_time
                    synced = True
                """
                self.process_event(e)

    def get_occupancy(self, animals=None, old_format=True):
        if animals is None:
            animals = list(self.animals.keys())
        o = []
        for a in animals:
            o.extend(copy.copy(self.animals[a].occupancy))
            #ai = int(a, 16)
            #for i in self.animals[a].occupancy:
            #    o.append(i + [ai, ])
        o.sort(key=lambda i: i[1].world_timestamp)
        if not old_format:
            return o
        oo = []
        for i in o:
            # [st, et, cage, animal, 0]
            oo.append([
                i[1].world_timestamp, i[2].world_timestamp, i[0],
                int(i[1].data0, 16), 0])
        oo = numpy.array(oo)
        #oo[:, 0] *= 1000.
        #oo[:, 1] *= 1000.
        return oo.astype('i8')
    
    def get_chase_matrix(self, animals=None):
        if animals is None:
            animals = sorted(list(self.animals.keys()))
        n = len(animals)
        maes = numpy.zeros((n, n))
        ti = lambda aid: animals.index(aid)
        for t in self.tubes:
            for mae in t.multi_animal_events:
                chaser, chasee, _ = mae
                maes[ti(chaser), ti(chasee)] += 1
        return maes, animals