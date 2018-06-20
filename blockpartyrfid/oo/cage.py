#!/usr/bin/env python


class Cage(object):
    def __init__(self, number, animals=None):
        self.number = number
        if animals is None:
            animals = []
        self.animals = set(animals)