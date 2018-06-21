#!/usr/bin/env python


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

    def set_occupancy(self, cage, last_event, event):
        # log occupancy [cage, prior event, next event]
        self.occupancy.append([
            cage, last_event, event])

        # check against predicited cage
        if not len(self.predictions):
            return
        
        # get last prediction
        p = self.predictions[-1]
        assert p[1] == last_event
        # if correct, accept predictions
        if p[0] == cage:
            self.accept_predictions()

    def set_prediction(self, cage, event):
        self.predictions.append([cage, event])

    def accept_predictions(self):
        # predictions are [cage, enter event(has time)]
        # when accepted, stitch predictions onto previous occupancy
        assert len(self.occupancy) > 2
        current = self.occupancy[-1]
        previous = self.occupancy[-2]
        assert previous[2] == self.predicitions[0][1]
        assert current[1] == self.predictions[-1][1]
        cage, enter_event = self.predictions[0]
        for p in self.predictions[1:]:
            self.occupancy.append([
                cage, enter_event, p[1]])
            cage, enter_event = p
        # clear predictions
        self.predictions = []

    def clear_predictions(self, event):
        self.predicitions = []

    def get_predicted_cage(self):
        if not len(self.predictions):
            return None
        return self.predictions[-1][0]