#!/usr/bin/env python


#debug_animal = '2A006D2D1B'
#debug_animal = '2A006D4F9F'
#debug_animal = '2A006D5AF7'
debug_animal = None


class Animal(object):
    def __init__(self, rfid, name=None, **kwargs):
        self.rfid = rfid
        if name is None:
            name = str(rfid)
        self.name = name
        for k in kwargs:
            if k in ('name', 'rfid'):
                raise KeyError("Animal meta cannot be %s" % k)
            setattr(self, k, kwargs[k])
        
        self.last_read = None
        
        self.predictions = []
        self.occupancy = []
        
        self.reads_per_tube = {}
        self.teleports = []
    
    def was_read(self, tube, timestamp):
        if tube not in self.reads_per_tube:
            self.reads_per_tube[tube] = 1
        else:
            self.reads_per_tube[tube] += 1
    
    def get_n_reads(self):
        return sum(self.reads_per_tube.values())
    
    def teleported(self, time, old_tube, new_tube):
        self.teleports.append([time, old_tube, new_tube])

    def set_occupancy(self, cage, last_event, event):
        if self.rfid == debug_animal:
            print(
                "[%s]set_occupancy: %s, %s, %s, %s, %s" %
                (self.rfid, cage, last_event.timestamp, last_event.board, event.timestamp, event.board))

        current = [cage, last_event, event]
        # check against predicted cage
        if len(self.predictions):
            # get last prediction
            p = self.predictions[-1]
            assert p[1].board == last_event.board
            # if correct, accept predictions
            if p[0] == cage:
                self.accept_predictions(current)
                # and use the prediction for the occupancy
                current[1] = p[1]
            else:
                self.clear_predictions(event)

        # log occupancy [cage, prior event, next event]
        self.occupancy.append(current)

    def set_prediction(self, cage, event):
        if self.rfid == debug_animal:
            print("[%s]set_prediction: %s, %s, %s" % (self.rfid, cage, event.timestamp, event.board))
        self.predictions.append([cage, event])

    def accept_predictions(self, current):
        if self.rfid == debug_animal:
            print(
                "[%s]accept_predictions" %
                (self.rfid, ))
        # predictions are [cage, enter event(has time)]
        # when accepted, stitch predictions onto previous occupancy
        assert len(self.occupancy) > 0
        #current = self.occupancy[-1]
        previous = self.occupancy[-1]
        assert previous[2].board == self.predictions[0][1].board
        assert current[1].board == self.predictions[-1][1].board
        cage, enter_event = self.predictions[0]
        for p in self.predictions[1:]:
            self.occupancy.append([
                cage, enter_event, p[1]])
            cage, enter_event = p
        # clear predictions
        self.predictions = []

    def clear_predictions(self, event):
        if self.rfid == debug_animal:
            print(
                "[%s]clear_predictions: %s, %s" %
                (self.rfid, event.timestamp, event.board))
        self.predictions = []

    def get_predicted_cage(self):
        if not len(self.predictions):
            return None
        return self.predictions[-1][0]