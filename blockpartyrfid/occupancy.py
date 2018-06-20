#!/usr/bin/env python

import numpy

from . import consts
from . import db


def merge_occupancies(occupancies, cull=True):
    # merge
    if len(occupancies) > 1:
        occupancy = numpy.vstack(occupancies)
    else:
        occupancy = occupancies[0]

    # sort
    occupancy = occupancy[numpy.argsort(occupancy[:, 0])]
    if not cull:
        return occupancy

    # find conflicting
    n = len(occupancy)
    m = numpy.ones(n, dtype='bool')
    for i in range(n):
        if i == n - 1:
            continue
        i0 = i
        o = occupancy[i]

        i += 1
        cinds = []
        while i < n:
            # check next
            c = occupancy[i]
            if c[0] < o[1] and c[3] == o[3]:
                # conflict
                cinds.append(i)
                # print("Found conflict:", o, occupancy[i][0], i, i0)
            elif c[0] > o[1]:
                i = n
            i += 1
        if len(cinds) == 0:
            continue
        c = occupancy[[i0, ] + cinds]
        # make sure all times agree
        sad = numpy.sum(numpy.abs(numpy.diff(c[:, :2], axis=0)))
        if sad != 0:
            raise Exception()
        # pick one with largest confidence
        ci = numpy.argmax(numpy.abs(c[:, 4]))
        for i in cinds:
            if i == ci:
                continue
            m[i] = False
        #if abs(c[4]) > abs(o[4]):
        #    m[i0] = False
        #else:
        #    m[cinds[0]] = False
    return occupancy[m]


def from_tube_sequence(rfid_reads):
    # find first 0->1 or 1->0 or 1->2 or 2->1...?
    # if 0->1, was in cage 1 between, now in cage 2
    #   if next is 0, invalid!
    #   if next is 1, moved to cage 1
    #   if next is 2, moved to cage 3
    # if 1->0, was in cage 1 between, now in cage 0
    #   if next is 0, moved to cage 1
    #   if next is 1, invalid!
    # valid tubes are cage - 1 or cage
    starts = []
    start_i = {}
    n = len(rfid_reads)
    for i in range(n-1):
        if abs(rfid_reads[i, 1] - rfid_reads[i+1, 1]) == 1:
            # moved cages
            starts.append({
                'i': i,
                'cage': max(rfid_reads[i, 1], rfid_reads[i+1, 1]),
                'start': rfid_reads[i, 0],
                'end': rfid_reads[i+1, 0],
                'forward_chain': [],
                'backward_chain': [],
            })
            start_i[i] = starts[-1]
    # for each start, trace out the sequence of cages
    for start in starts:
        i = start['i']
        cage = start['cage']
        chain = start['forward_chain']
        # at start['i'] animal entered start['cage']
        # trace forward (until next start, or end)
        i += 1
        while i < n - 1:
            r = rfid_reads[i]
            tube = r[1]
            if tube == cage:
                cage += 1
            elif tube == (cage - 1):
                cage -= 1
            else:
                # invalid move
                break
            if i in start_i:
                if cage != start_i[i]['cage']:
                    break
            chain.append((i, cage))
            i += 1
        i = start['i']
        cage = start['cage']
        chain = start['backward_chain']
        # trace backward (until previous start, or beginning)
        while i >= 1:
            r = rfid_reads[i]
            tube = r[1]
            if tube == cage:
                cage += 1
            elif tube == cage - 1:
                cage -= 1
            else:
                # invalid move
                break
            chain.append((i - 1, cage))
            i -= 1
    return starts


def merge_sequences(sequences):
    od = {}
    hits = 0
    for si in range(len(sequences)):
        s = sequences[si]
        if si != len(sequences) - 1:
            n = sequences[si + 1]
            # only count hits
            if (n['i'], n['cage']) in s['forward_chain']:
                hits += 1
                for i in s['forward_chain']:
                    od[i[0]] = od.get(i[0], []) + [i[1], ]
        if si != 0:
            p = sequences[si - 1]
            if (p['i'], p['cage']) in s['backward_chain']:
                for i in s['backward_chain']:
                    od[i[0]] = od.get(i[0], []) + [i[1], ]
    # compute reliability score
    reliability = hits / float(len(sequences) - 1)
    for i in od:
        l = list(set(od[i]))
        if len(l) == 1:
            od[i] = l[0]
        else:
            od[i] = l
    for si in sequences:
        od[si['i']] = si['cage']
    return od, reliability


def merged_sequence_to_occupancy(sequence, reads):
    # sequence: dict with key = read index, value = cage
    animal = list(set(reads[:, consts.RFID_ID_COLUMN]))
    if len(animal) != 1:
        raise Exception
    animal = animal[0]
    inds = numpy.array(sorted(sequence.keys()))
    # [start, end, cage, animal, direction?]
    occupancy = []
    # cage from inds[i] to inds[i+1]
    for (i, ind) in enumerate(inds[:-1]):
        c = sequence[ind]
        if isinstance(c, list):
            continue
        st = reads[ind, 0]
        et = reads[inds[i + 1], 0]
        occupancy.append([st, et, c, animal, 0])
    return numpy.array(occupancy)


def find_multi_animal_events(rfid_reads, threshold):
    reads = numpy.vstack(rfid_reads.values())
    reads = reads[reads[:, consts.TIME_COLUMN].argsort()]
    boards = numpy.unique(reads[:, consts.BOARD_COLUMN])
    maes = []
    for board in boards:
        br = reads[reads[:, consts.BOARD_COLUMN] == board]
        starts = numpy.where(
            numpy.diff(br[:, consts.TIME_COLUMN]) < threshold)[0]
        n = len(br)
        used = []
        for start in starts:
            if start in used:
                continue
            # find all contributing events
            index = start + 1
            used.append(start)
            while index < n:
                if (
                        br[index, consts.TIME_COLUMN] -
                        br[index - 1, consts.TIME_COLUMN] < threshold):
                    used.append(index)
                    index += 1
                else:
                    break
            evs = br[start:index]
            maes.append({
                'times': evs[:, consts.TIME_COLUMN],
                'animals': evs[:, consts.RFID_ID_COLUMN],
                'board': board,
            })
    return sorted(maes, key=lambda i: i['times'][0])


def generate_chase_matrix(multi_animal_events, board=None, animals=None):
    if board is None:
        tb = lambda b: True
    else:
        tb = lambda b: board == b
    chase_dict = {}
    for e in multi_animal_events:
        if not tb(e['board']):
            continue
        chaser = e['animals'][-1]
        chased = e['animals'][:-1][::-1]
        if chaser not in chase_dict:
            chase_dict[chaser] = {}
        for c in chased:
            if c not in chase_dict[chaser]:
                chase_dict[chaser][c] = 1
            else:
                chase_dict[chaser][c] += 1
    if animals is None:
        animals = list(chase_dict.keys())
        [animals.extend(list(chase_dict[a].keys())) for a in chase_dict]
        animals = sorted(list(set(animals)))
    n = len(animals)
    chase_matrix = numpy.zeros((n, n))
    for (i, a) in enumerate(animals):
        for (j, b) in enumerate(animals):
            chase_matrix[i, j] = chase_dict.get(a, {}).get(b, 0)
    return chase_matrix, animals
