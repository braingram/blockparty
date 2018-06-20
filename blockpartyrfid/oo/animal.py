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