#!/usr/bin/env python


class Tube(object):
    def __init__(self, number):
        self.number = number
        self.multi_animal_events = []
        self.latest_reads = {}
        self.multi_animal_event_threshold = None
    
    def read_animal(self, rfid, timestamp):
        self.latest_reads[rfid] = timestamp
        if self.multi_animal_event_threshold is None:
            return
        for aid in list(self.latest_reads.keys()):
            if aid != rfid:
                ots = self.latest_reads[aid]
                if (
                        timestamp - self.latest_reads[aid] <
                        self.multi_animal_event_threshold):
                    # rfid chased/followed aid through the tube
                    # [chaser, chasee, time]
                    self.multi_animal_events.append([
                        rfid, aid, timestamp])