#!/usr/bin/env python

import numpy

from . import consts
from . import db


event_weights = {
    consts.EVENT_BEAM: 2,
    consts.EVENT_TOUCH_BINARY: 1,
}

state_weights = {
    consts.EVENT_BEAM: {
        consts.BEAM_BROKEN: 2,
        consts.BEAM_UNBROKEN: 1,
    },
    consts.EVENT_TOUCH_BINARY: {
        consts.TOUCH_TOUCHED: 2,
        consts.TOUCH_UNTOUCHED: 1,
    }
}
    

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


def from_rfid_sequence(events, as_dict=False):
    # get all valid rfid events
    rfid = db.sel(events, event=consts.EVENT_RFID, data1=consts.RFID_VALID)

    # get all animal ids
    aids = db.all_animals(rfid)

    occupancy = {}
    # for each animal
    for aid in aids:
        aevs = db.sel(rfid, data0=aid)
        # find times where sequence reads are on different boards
        board_changes = numpy.diff(aevs[:, consts.BOARD_COLUMN])
        # find indices of rfid events that resulted in a change
        ci = numpy.where(numpy.abs(board_changes) == 1)[0]
        if len(ci) is None:
            continue

        # find entrances and exits
        entrances = aevs[ci]
        exits = aevs[ci + 1]

        # copy entrances to use as result
        t = entrances.copy()

        # determine cage # (maximum board number)
        t[:, 2] = numpy.maximum(
            entrances[:, consts.BOARD_COLUMN],
            exits[:, consts.BOARD_COLUMN])

        # copy exit times
        t[:, 1] = exits[:, consts.TIME_COLUMN]

        t[:, 4] = 10.
        occupancy[aid] = t[:, :5]

    if not as_dict:
        a = numpy.vstack(occupancy.values())
        return a[numpy.argsort(a[:, consts.TIME_COLUMN])]
    return occupancy


def measure_rfid_reads(events, board=None):
    if board is None:
        bids = db.all_boards(events)
        vs = [measure_rfid_reads(events, board=bid) for bid in bids]
        [vs[0].extend(v) for v in vs[1:]]
        vs = vs[0]
        # TODO recombine all boards
        return sorted(vs, key=lambda i: i['timestamp'])
    
    arfids = db.sel(events, event='rfid')
    brfids = db.sel(arfids, board=board)
    bevents = db.split_events(db.sel(events, board=board), board=False)
    
    data = []
    for (i, brfid) in enumerate(brfids):
        timestamp, board_id, _, animal_id, _ = brfid
        d = {
            'rfid': {},
            'timestamp': timestamp,
            'board_id': board_id,
            'animal_id': animal_id,
        }
        # measure times of next and previous rfid for this board
        if (i == 0):
            d['rfid']['prev_board'] = None
        else:
            d['rfid']['prev_board'] = brfids[i - 1, consts.TIME_COLUMN]
        if (i == len(brfids) - 1):
            d['rfid']['next_board'] = None
        else:
            d['rfid']['next_board'] = brfids[i + 1, consts.TIME_COLUMN]
        
        # find events for next and previous rfid for this animal
        animal_rfids = db.sel(arfids, data0=animal_id)
        for (j, a) in enumerate(animal_rfids):
            if a[consts.TIME_COLUMN] == timestamp:
                if (j == 0):
                    d['rfid']['prev_animal'] = None
                else:
                    d['rfid']['prev_animal'] = animal_rfids[j - 1]
                if (j == len(animal_rfids) - 1):
                    d['rfid']['next_animal'] = None
                else:
                    d['rfid']['next_animal'] = animal_rfids[j + 1]
                break
        # (save these for reconstructing occupancy)
        # if no next/previous, use either -inf or +inf?
        # measure dt for neighbors
        
        # find closest beam/touch break/touch
        sd = {}
        for evt in (consts.EVENT_BEAM, consts.EVENT_TOUCH_BINARY):
            sd[evt] = {}
            for side in consts.sides[evt]:
                triggered, released = consts.states[evt]
                te = db.closest_event(
                    bevents[evt][side][triggered],
                    timestamp)
                if te is not None:
                    te = te[consts.TIME_COLUMN]
                sd[evt][side] = {triggered: te}
                if te is None:
                    sd[evt][side][released] = None
                else:
                    re = db.next_event(
                        bevents[evt][side][released],
                        te)
                    if re is not None:
                        re = re[consts.TIME_COLUMN]
                    sd[evt][side][released] = re
                
                # get times of next/previous beam/touch break/unbreak
                # measure dt for events
        d['sensors'] = sd
        data.append(d)

        # score read by dt of events
        # generate liberal occupancy
    
    # merge and remove conflicts from occupancy
    return data


def measured_rfid_reads_to_occupancy(
        mrfids, sensor_timeout=2000, threshold=0,
        start_time=None, end_time=None):
    if start_time is None:
        start_time = mrfids[0]['timestamp']
    if end_time is None:
        end_time = mrfids[-1]['timestamp']
    occupancy = []
    evs = (consts.EVENT_BEAM, consts.EVENT_TOUCH_BINARY)
    for d in mrfids:
        sd = d['sensors']
        direction = 0
        # assign a direction
        for evt in evs:
            ew = event_weights[evt]
            left, right = consts.sides[evt]
            for state in consts.states[evt]:
                sw = state_weights[evt][state]
                lt = sd[evt][left][state]
                rt = sd[evt][right][state]
                if lt is not None and rt is not None:
                    if (
                            (abs(lt - d['timestamp']) < sensor_timeout) and
                            (abs(rt - d['timestamp']) < sensor_timeout)):
                        if (lt > rt):
                            direction -= (sw * ew)
                        else:
                            direction += (sw * ew)
        # output occupancy
        if abs(direction) > threshold and direction != 0:
            if direction > 0:
                # right move
                before, after = 0, 1
            elif direction < 0:
                # left move
                before, after = 1, 0
            # enter, exit, cage, animal, confidence
            if d['rfid']['prev_animal'] is not None:
                st = d['rfid']['prev_animal'][consts.TIME_COLUMN]
            else:
                st = start_time
            occupancy.append([
                st, d['timestamp'],
                d['board_id'] + before, d['animal_id'], direction])
            if d['rfid']['next_animal'] is not None:
                et = d['rfid']['next_animal'][consts.TIME_COLUMN]
            else:
                et = end_time
            occupancy.append([
                d['timestamp'], et,
                d['board_id'] + after, d['animal_id'], direction])
    return occupancy


def by_isolated_transitions(
        events, board, timeout=2000,
        threshold=4):
    rfid = db.sel(events, event='rfid')

    # get events for this board
    brfid = db.sel(rfid, board=board)
    bevents = db.sel(events, board=board)

    # TODO assumes events from only 1 board!
    # find isolated transitions:
    #  - no rfid read within +- 2000 ms (start with this)
    rfid_dt = numpy.diff(brfid[:, consts.TIME_COLUMN])
    rfid_mask = numpy.ones(brfid.shape[0], dtype='bool')
    binds = numpy.where(rfid_dt < timeout)[0]
    binds[binds == (len(rfid_mask) - 1)] = len(rfid_mask) - 2
    rfid_mask[binds] = False
    rfid_mask[binds + 1] = False

    # get isolated rfid events
    irfid = brfid[rfid_mask]
    irfid_inds = numpy.where(rfid_mask)[0]

    irfid_dict = [
        {
            'event': ev,
            'i': i,
            't': ev[consts.TIME_COLUMN],
            'b': ev[consts.BOARD_COLUMN],
            'a': ev[consts.RFID_ID_COLUMN],
            'd': {},
        } for (i, ev) in zip(irfid_inds, irfid)]

    # find beam/touch break/unbreak for left/right for each isolated event
    i_ts = irfid[:, consts.TIME_COLUMN]
    sevs = db.split_events(bevents, board=False)

    # sevs[event_type][side][state], m
    for et in (consts.EVENT_BEAM, consts.EVENT_TOUCH_BINARY):
        if et == consts.EVENT_BEAM:
            sides = (consts.BEAM_LEFT, consts.BEAM_RIGHT)
            active, inactive = (consts.BEAM_BROKEN, consts.BEAM_UNBROKEN)
        else:
            sides = (consts.TOUCH_LEFT, consts.TOUCH_RIGHT)
            active, inactive = (consts.TOUCH_TOUCHED, consts.TOUCH_UNTOUCHED)
        for side in sides:
            aevs = sevs[et][side][active]  # active events
            ievs = sevs[et][side][inactive]  # inactive events
            # find closest broken/touched event
            adj = db.find_adjacent(irfid, aevs)  # adjacent times

            # for each valid adjacent time, find next inactive event
            for (i, a) in enumerate(adj):
                if et not in irfid_dict[i]['d']:
                    irfid_dict[i]['d'][et] = {}
                a_t = a[numpy.nanargmin(numpy.abs(a[:2] - irfid_dict[i]['t']))]
                if numpy.isnan(a_t):
                    # invalid, use None for both
                    a_t, i_t = None, None
                else:
                    i_ev = db.sel(ievs, timerange=(a_t, a_t + timeout))
                    if len(i_ev):
                        i_t = i_ev[0, consts.TIME_COLUMN]
                    else:
                        i_t = None
                irfid_dict[i]['d'][et][side] = [a_t, i_t]

    occupancy = []
    # needs access to all rfid events not just the ones for this board
    aevs = db.by_animal(rfid)
    # for each irfid_dict, compute the dt for beam/touch and active/inactive
    # if they all agree, consider this a transition
    # maybe score by how many agree
    # ba_dt = 1, bi_dt = 1, ta_dt, ti_dt
    for i in irfid_dict:
        i['dt'] = {}
        i['direction'] = 0
        for et in (consts.EVENT_BEAM, consts.EVENT_TOUCH_BINARY):
            # TODO deal with touch left != beam left
            a_l, i_l = i['d'][et][consts.BEAM_LEFT]
            a_r, i_r = i['d'][et][consts.BEAM_RIGHT]
            if (a_l is not None) and (a_r is not None):
                a_dt = a_l - a_r
                if a_l < a_r:
                    i['direction'] += 1
                else:
                    i['direction'] -= 1
            else:
                a_dt = None
            if (i_l is not None) and (i_r is not None):
                i_dt = i_l - i_r
                if i_l < i_r:
                    i['direction'] += 1
                else:
                    i['direction'] -= 1
            else:
                i_dt = None
            i['dt'][et] = [a_dt, i_dt]
        if abs(i['direction']) >= threshold:
            if i['direction'] > 0:
                before, after = 0, 1
            else:
                before, after = 1, 0
            # TODO valid transition, mark occupancy before and after
            # [enter time, exit time, cage #, animal #, threshold]
            # find this event
            evs = aevs[i['a']]
            evi = numpy.where(evs[:, consts.TIME_COLUMN] == i['t'])[0]
            if len(evi) != 1:
                raise Exception("Failed to re-find rfid event")
            evi = evi[0]
            if evi != 0:  # log before
                enter_time = evs[evi - 1][consts.TIME_COLUMN]
                exit_time = i['t']
                cage_n = i['b'] + before
                occupancy.append(
                    [enter_time, exit_time, cage_n, i['a'], i['direction']])
            elif evi != len(evs) - 1:  # log after
                enter_time = i['t']
                exit_time = evs[evi + 1][consts.TIME_COLUMN]
                cage_n = i['b'] + after
                occupancy.append(
                    [enter_time, exit_time, cage_n, i['a'], i['direction']])
    return numpy.array(occupancy), irfid_dict

    
def assign_direction_to_tube_events(te):
    for e in te:
        ni = len(set([i[3] for i in e['i']]))
        nl = len(e['l'])
        nr = len(e['r'])
        if nl == 1 and nr == 1:  # assign direction
            if e['l'][0][0] < e['r'][0][0]:  # moving right
                e['direction'] = 'r'
            else:
                e['direction'] = 'l'
        else:
            e['direction'] = '?'


def tube_events_to_occupancy(te):
    # state of each animal
    # animal_id: {
    #   previous: previous tube event (either for this animal or unassigned)
    state = {}
    last_unassigned = None
    occupancy = []
    for e in te:
        if e['direction'] == '?':
            # if previous event for this animal had a direction
            # assign occupancy over that period
            for a in e['animals']:
                if a in state:
                    if state[a]['previous']['direction'] != '?':
                        occupancy.append([
                            state[a]['previous']['end'],
                            e['start'],
                            'lr'.index(state[a]['previous']['direction']),
                            a,
                            -1])
                    # else previous direction is '?', do nothing
                else:
                    state[a] = {'previous': e}
            for a in state:
                state[a]['previous'] = e
            last_unassigned = e
        else:  # this transition has a direction l/r
            for a in e['animals']:
                if a in state:
                    # TODO check for conflicts
                    # fill from previous till now
                    pe = state[a]['previous']
                    occupancy.append([
                        pe['end'], e['start'],
                        1 - 'lr'.index(e['direction']),
                        a,
                        'lr'.index(e['direction'])])
                else:  # first event for this animal
                    if last_unassigned is not None:
                        pe = last_unassigned
                        occupancy.append([
                            pe['end'], e['start'],
                            1 - 'lr'.index(e['direction']),
                            a,
                            'lr'.index(e['direction'])])
                    else:
                        # TODO assign fromt start time?
                        pass
                    state[a] = {'previous': e}
                state[a]['previous'] = e
    # TODO assign to end time
    return occupancy


def merge_tube_event_occupancys(o0, o1):
    # each occupancy has only left right
    # right for o0 could be anything in o1
    # left for o1 could be anything for o0
    # conflicts could be:
    # - simultaneuous reporting of left o0 and right o1
    # - jumps from left o0 to right o1
    
    # start at index 0 for each
    occupancy = []
    # get copy of arrays to allow modification during iteration
    o0 = numpy.array(o0, copy=True)
    o1 = numpy.array(o1, copy=True)
    # offset cage numbers for o1
    o1[:, 2] += 1
    i0, i1 = 0, 0
    while i0 < len(o0) and i1 < len(o1):
        e0 = o0[i0]
        e1 = o1[i1]
        # check if these overlap
        if e0[1] < e1[0]:
            # accept e0, continue
            occupancy.append(list(e0))
            i0 += 1
            continue
        elif e1[1] < e1[0]:
            # accept e1, continue
            occupancy.append(list(e1))
            i1 += 1
            continue
        if e0[3] != e1[3]:  # not the same animal
            if e0[1] < e1[1]:
                occupancy.append(list(e0))
                i0 += 1
            else:
                occupancy.append(list(e1))
                i1 += 1
            continue
        # events overlap, same animal, combine & check for conflict
        if e0[1] < e1[1]:
            # e0 ends before e1
            if e0[0] > e1[0]:
                # e0 is 'inside' e1
                # assign occupancy from start of e1 to start of e0
                occupancy.append([e1[0], e0[0], e1[2], e1[3], -2])
            # else, e0 preceeds e1
            # assign occupancy from start of e0 to end of e0
            occupancy.append([e0[0], e0[1], e0[2], e0[3], -3])
            # then modify e1 start to end of e0
            e1[0] = e0[1]
            # advance e0
            i0 += 1
        else:
            # e1 ends before e0
            if e1[0] < e0[0]:
                # e1 is 'inside' e0
                # assign occupancy from start of e0 to start of e1
                occupancy.append([e0[0], e1[0], e0[2], e0[3], -4])
            # else e1 preceeds e1
            # assign occupancy from start of e1 to end of e1
            occupancy.append([e1[0], e1[1], e1[2], e1[3], -5])
            # then modify e0 start to end of e1
            e0[0] = e1[1]
            # advance e1
            i1 += 1
    # TODO finish out events
    return numpy.array(occupancy)