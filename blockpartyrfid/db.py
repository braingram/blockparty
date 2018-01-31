#!/usr/bin/env python

import os
import sys

import numpy

from . import consts
from . import io


if sys.version_info.major > 2:
    unicode = str



def sel(vs, board=None, event=None, data0=None, data1=None, timerange=None):
    if isinstance(event, (str, unicode)):
        event = consts.event_strings[event]
    if isinstance(data0, (str, unicode)):
        data0 = consts.data_strings[event][0][data0]
    if isinstance(data1, (str, unicode)):
        data1 = consts.data_strings[event][1][data1]
    m = numpy.ones(vs.shape[0], dtype='bool')
    if board is not None:
        m &= (vs[:, consts.BOARD_COLUMN] == board)
    if event is not None:
        m &= (vs[:, consts.EVENT_COLUMN] == event)
    if data0 is not None:
        m &= (vs[:, consts.DATA0_COLUMN] == data0)
    if data1 is not None:
        m &= (vs[:, consts.DATA1_COLUMN] == data1)
    if timerange is not None:
        assert len(timerange) == 2
        m &= (vs[:, consts.TIME_COLUMN] < timerange[1])
        m &= (vs[:, consts.TIME_COLUMN] > timerange[0])
    return vs[m]


def remap_ids(evs, rmap):
    # rmap: {old key: new key...}
    for k in rmap:
        evs[
            (evs[:, consts.DATA0_COLUMN] == k) &
            (evs[:, consts.EVENT_COLUMN] == consts.EVENT_RFID),
            consts.DATA0_COLUMN] = rmap[k]


def _reduce_dict(d):
    if isinstance(d, (list, tuple, numpy.ndarray)):
        return d
    if isinstance(d, dict):
        if len(d.keys()) == 1 and list(d.keys())[0] is None:
            return _reduce_dict(d[None])
        else:
            return {k: _reduce_dict(d[k]) for k in d}
    raise TypeError("Cannot reduce type: %s" % type(d))


def split_events(vs, board=True, event=True, data0=True, data1=True):
    svs = {}
    if board:
        bids = all_boards(vs)
    else:
        bids = [None, ]
    if event:
        evs = numpy.unique(vs[:, consts.EVENT_COLUMN])
    else:
        evs = [None, ]
    for bid in bids:
        svs[bid] = {}
        for ev in evs:
            d = sel(vs, board=bid, event=ev)
            if data0:
                d0s = numpy.unique(d[:, consts.DATA0_COLUMN])
            else:
                d0s = [None, ]
            if data1:
                d1s = numpy.unique(d[:, consts.DATA1_COLUMN])
            else:
                d1s = [None, ]
            svs[bid][ev] = {}
            for d0 in d0s:
                svs[bid][ev][d0] = {}
                for d1 in d1s:
                    svs[bid][ev][d0][d1] = sel(d, data0=d0, data1=d1)
    # re-combine
    return _reduce_dict(svs)


def all_boards(vs):
    return numpy.unique(vs[:, consts.BOARD_COLUMN])


def all_animals(vs):
    return numpy.unique(
        sel(vs, event='rfid', data1=0)[:, consts.RFID_ID_COLUMN])


def by_animal(events):
    aids = all_animals(events)
    return {aid: sel(events, event='rfid', data0=aid) for aid in aids}


def find_adjacent(a, b, return_mask=False):
    """for each event in a, find the next, and previous event in b
    return [previous_b_time, next_b_time, previous_b_index, next_b_index]
    None for time/index if no event was found
    """
    a_times = a[:, consts.TIME_COLUMN]
    b_times = b[:, consts.TIME_COLUMN]
    ninds = numpy.searchsorted(b_times, a_times, side='right')
    pmask = ninds == 0
    nmask = ninds == len(b_times)
    ninds[pmask] = 0
    ninds[nmask] = 0
    r = numpy.empty([len(a_times), 4], dtype='f8')
    r[:, 0] = b_times[ninds - 1]
    r[:, 1] = b_times[ninds]
    r[:, 2] = ninds - 1
    r[:, 3] = ninds

    # set invalid times/indices to nan
    r[pmask, 0] = numpy.nan
    r[pmask, 2] = numpy.nan
    r[nmask, 1] = numpy.nan
    r[nmask, 3] = numpy.nan
    if return_mask:
        return r, numpy.logical_and(pmask, nmask)
    return r


def select_events_by_duration(bd, min_t=100, max_t=5000):
    """returns events with
        [time, board, type, bd[:,3], duration]
    """
    # find transitions and calculate durations
    bb = numpy.diff(bd, axis=0)
    # take all falling edges
    bm = bb[:, 4] == -1
    # get start times
    ts = bd[:-1][bm]
    # and durations
    ds = bb[bm][:, 0]
    # find all with duration > min_t
    dm = numpy.logical_and(ds > min_t, ds < max_t)
    # return times and durations
    cts = ts[dm].copy()
    cts[:, 4] = ds[dm]
    return cts


def closest_event(evs, t, max_dt=None):
    dts = numpy.abs(evs[:, consts.TIME_COLUMN] - t)
    i = dts.argmin()
    if max_dt is not None and dts[i] > max_dt:
        return None
    return evs[i]


def next_event(evs, t, max_dt=None):
    dts = evs[:, consts.TIME_COLUMN] - t
    dts[dts < 0] = dts.max()
    i = dts.argmin()
    if max_dt is not None and dts[i] > max_dt:
        return None
    return evs[i]


def sum_range(a):
    """ sum ranges [column 0 = start_time, column 1 = end_time]
    without double counting overlaps"""
    s = 0
    if len(a) == 0:
        return s
    for i in range(len(a) - 1):
        if a[i, 1] > a[i + 1, 0]:
            s += a[i + 1, 0] - a[i, 0]
        else:
            s += a[i, 1] - a[i, 0]
    s += a[-1, 1] - a[-1, 0]
    return s


def beam_events_to_duration(be, min_duration=None):
    if len(numpy.unique(be[:, consts.DATA0_COLUMN])) != 1:
        raise Exception("events must be pre-split into left/right")
    while (be[0, consts.DATA1_COLUMN] != 1):
        be = be[1:]
    while (be[-1, consts.DATA1_COLUMN] != 0):
        be = be[:-1]
    d = be[::2].copy()
    d[:, 1] = be[1::2, consts.TIME_COLUMN]
    d[:, 2] = d[:, 1] - d[:, 0]
    if min_duration is not None:
        d = d[d[:, 2] >= min_duration]
    return d[:, :3]


def rfid_events_to_duration(re, min_duration=None):
    while (
            (re[0, consts.DATA1_COLUMN] != 1) or
            (re[0, consts.DATA0_COLUMN] != 1)):
        re = re[1:]
    while (
            (re[-1, consts.DATA1_COLUMN] != 1) or
            (re[-1, consts.DATA0_COLUMN] != 0)):
        re = re[:-1]
    d = re[::3].copy()
    d[:, 1] = re[2::3, consts.TIME_COLUMN]
    d[:, 2] = d[:, 1] - d[:, 0]
    d[:, 3] = re[1::3, consts.DATA0_COLUMN]
    if min_duration is not None:
        d = d[d[:, 2] >= min_duration]
    return d[:, :4]


def find_overlapping_durations(a, b, margin=None):
    if margin is None:
        margin = [0, 0]
    inds = []
    for ai in xrange(len(a)):
        sa = a[ai]
        st = sa[0] - margin[0]
        et = sa[1] + margin[1]
        i = numpy.where(
            numpy.logical_not((b[:, 0] > et) | (b[:, 1] < st)))[0]
        #i = numpy.where(
        #    ((b[:, 0] < st) & (b[:, 1] > st)) |
        #    ((b[:, 0] < et) & (b[:, 1] > et)))[0]
        inds.append(list(i))
    return inds


def find_neighbors(index, key, omap, inds=None, visited=None):
    if inds is None:
        inds = {'l': [], 'r': [], 'i': []}
        visited = {'l': set(), 'r': set(), 'i': set()}
    if index in visited[key]:
        return inds
    visited[key].add(index)
    okeys = {
        'r': ['l', 'i'],
        'l': ['r', 'i'],
        'i': ['l', 'r']}[key]
    for okey in okeys:
        for oi in omap[key][okey][index]:
            if oi in visited[okey]:
                continue
            inds[okey].append(oi)
            # recurse
            find_neighbors(oi, okey, omap, inds, visited)
    return inds


def generate_overlap_map(le, re, ie, margin=None):
    return {
        'l': {
            'r': find_overlapping_durations(le, re),
            'i': find_overlapping_durations(le, ie, margin),
        },
        'r': {
            'l': find_overlapping_durations(re, le),
            'i': find_overlapping_durations(re, ie, margin),
        },
        'i': {
            'l': find_overlapping_durations(ie, le, margin),
            'r': find_overlapping_durations(ie, re, margin),
        }
    }


def find_tube_events(
        board_events, margin=None, min_duration=None,
        ignore_tails=True, remove_conflicts=True):
    boards = numpy.unique(board_events[:, consts.BOARD_COLUMN])
    if len(boards) != 1:
        raise Exception("Only works for 1 board")
    board = boards[0]
    # find left/right beam events
    lbe = beam_events_to_duration(
        sel(board_events, event='beam', data0=consts.BEAM_LEFT), min_duration)
    rbe = beam_events_to_duration(
        sel(board_events, event='beam', data0=consts.BEAM_RIGHT), min_duration)
    ie = rfid_events_to_duration(
        sel(board_events, event='rfid'))
    ed = {'l': lbe, 'r': rbe, 'i': ie}
    # find overlapping beam durations
    omap = generate_overlap_map(lbe, rbe, ie, margin)
    # merge beam durations
    tube_events = []
    visited = set()
    for ri in xrange(len(rbe)):
        if ri in visited:
            continue
        # for each index in right, find 'neighbors'
        inds = find_neighbors(ri, 'r', omap)
        inds['r'].append(ri)
        for k in inds:
            inds[k].sort()
        [visited.add(ri) for ri in inds['r']]

        if len(inds['l']) == 0:
            continue

        # find start/end times
        st = ed['r'][ri][0]
        et = ed['r'][ri][1]
        for k in inds:
            for i in inds[k]:
                d = ed[k][i]
                st = min(st, d[0])
                et = max(et, d[1])
        direction = '?'
        if len(inds['l']) == 1 and len(inds['r']) == 1:
            l = ed['l'][inds['l'][0]][0]
            r = ed['r'][inds['r'][0]][0]
            if l < r:
                direction = 'r'
            else:
                direction = 'l'
        duration = et - st
        te = {
            'start': st,
            'end': et,
            'board': board,
            'duration': duration,
            'animals': set([ed['i'][i][3] for i in inds['i']]),
            'direction': direction,
        }
        for k in 'lri':
            te[k] = numpy.array([ed[k][i] for i in inds[k]])
        if len(te['animals']) == 0:
            continue
        tube_events.append(te)
    if ignore_tails:
        assign_direction_ignoring_tails(tube_events)
    if remove_conflicts:
        unassign_conflicting_tube_event_directions(tube_events)
    return tube_events


def unassign_conflicting_tube_event_directions(te):
    state = {}
    cs = []
    for (i, e) in enumerate(te):
        if e['direction'] == '?':
            for a in state:
                state[a] = '?'
            continue
        # conflict = False
        for a in e['animals']:
            if a in state and state[a] == e['direction']:  # conflict
                # conflict = True
                cs.append(i)
            state[a] = e['direction']
        # if conflict:
        #     e['direction'] = '?'
        #     for a in state:
        #         state[a] = '?'
    for c in cs:
        te[c]['direction'] = '?'


def assign_direction_ignoring_tails(te):
    for e in te:
        if e['direction'] != '?':
            continue
        # don't apply this to >1 animal events
        if len(e['animals']) > 1:
            continue
        if (
                numpy.all(e['l'][1:, 2] < e['l'][0, 2] / 2.) and
                numpy.all(e['r'][1:, 2] < e['r'][0, 2] / 2.)):
            if e['l'][0, 0] < e['r'][0, 0]:
                e['direction'] = 'r'
            else:
                e['direction'] = 'l'


def assign_images_to_tube_events(te, image_directory):
    ims = io.get_images(image_directory)
    for e in te:
        st, et = e['start'], e['end']
        eims = ims[(ims['t'] >= st) & (ims['t'] <= et)]
        e['ims'] = {}
        eims = eims[numpy.argsort(eims['t'])]
        for eim in eims:
            fn = os.path.join(image_directory, eim['fn'])
            e['ims'][eim['t']] = fn


def h0(e):
    """1 animal, 1 left, 1 right, rising & falling edges agree"""
    lvl = 0
    if len(e['animals']) != 1:
        return lvl, False, None
    if len(e['l']) != 1 or len(e['r']) != 1:
        return lvl, False, None
    l, r = e['l'][0], e['r'][0]
    if l[0] < r[0] and l[1] < r[1]:
        return lvl, True, 'r'
    if l[0] > r[0] and l[1] > r[1]:
        return lvl, True, 'l'
    return lvl, False, None

    if e['duration'] > 1500:  # use falling edge
        return lvl, False, None
    if l[0] < r[0]:
        if l[1] < r[1]:
            return lvl, True, 'r'
        return lvl, False, None
    if l[1] > r[1]:
        return lvl, True, 'l'
    return lvl, False, None


def h1(e):
    """1 animal, 1 left, 1 right, rising & falling edges disagree"""
    lvl, valid, direction = h0(e)
    if valid:
        return lvl, valid, direction
    lvl = 1
    if len(e['animals']) != 1:
        return lvl, False, None
    if len(e['l']) != 1 or len(e['r']) != 1:
        return lvl, False, None
    l, r = e['l'][0], e['r'][0]
    if e['duration'] < 1500:  # use rising edge
        if l[0] < r[0]:
            return lvl, True, 'r'
        return lvl, True, 'l'
    # else use falling edge
    if l[1] < r[1]:
        return lvl, True, 'r'
    return lvl, True, 'l'


def h2(e):
    """>1 animal, 1 left or 1 right, agree"""
    lvl, valid, direction = h1(e)
    if valid:
        return lvl, valid, direction
    lvl = 2
    if len(e['animals']) < 2:
        return lvl, False, None
    if len(e['l']) != 1 or len(e['r']) != 1:
        return lvl, False, None
    l, r = e['l'][0], e['r'][0]
    if l[0] < r[0] and l[1] < r[1]:
        return lvl, True, 'r'
    if l[0] > r[0] and l[1] > r[1]:
        return lvl, True, 'l'
    return lvl, False, None

    if e['duration'] > 1500:  # use falling edge
        return lvl, False, None
    if l[0] < r[0]:
        if l[1] < r[1]:
            return lvl, True, 'r'
        return lvl, False, None
    if l[1] > r[1]:
        return lvl, True, 'l'
    return lvl, False, None


def h3(e):
    """>1 animal, 1 left or 1 right, disagree"""
    lvl, valid, direction = h2(e)
    if valid:
        return lvl, valid, direction
    lvl = 3
    if len(e['animals']) < 2:
        return lvl, False, None
    if len(e['l']) != 1 or len(e['r']) != 1:
        return lvl, False, None
    l, r = e['l'][0], e['r'][0]
    if e['duration'] < 1500:  # use rising edge
        if l[0] < r[0]:
            return lvl, True, 'r'
        return lvl, True, 'l'
    # else use falling edge
    if l[1] < r[1]:
        return lvl, True, 'r'
    return lvl, True, 'l'


def h4(e):
    """1 animal, >1 left, >1 right"""
    lvl, valid, direction = h3(e)
    if valid:
        return lvl, valid, direction
    lvl = 4
    if len(e['animals']) != 1:
        return lvl, False, None
    # TODO don't assign to duration > 10 seconds?
    # 1) do leading and trailing edges agree
    ls, rs = e['l'], e['r']
    if ls[0][0] < rs[0][0] and ls[-1][1] < rs[-1][1]:
        return lvl, True, 'r'
    if ls[0][0] > rs[0][0] and ls[-1][0] > rs[-1][1]:
        return lvl, True, 'l'
    # 2) if there is 1 left or 1 right, try to find tail of other one
    body = None
    if len(ls) == 1:
        # left is body, right is body + tail(s)
        # find right with closest duration
        l = ls[0]
        body = l[2]
        r = rs[numpy.argmin(numpy.abs(rs[:, 2] - l[2]))]
        if l[0] < r[0] and l[1] < r[1]:
            return lvl, True, 'r'
        if l[0] > r[0] and l[1] > r[1]:
            return lvl, True, 'l'
        # if e['duration'] < 1500:
    if len(rs) == 1:
        # right is body, left is body + tails(s)
        r = rs[0]
        body = r[2]
        l = ls[numpy.argmin(numpy.abs(ls[:, 2] - r[2]))]
        if l[0] < r[0] and l[1] < r[1]:
            return lvl, True, 'r'
        if l[0] > r[0] and l[1] > r[1]:
            return lvl, True, 'l'
    # 3) still no agreement, use falling edges that aren't tails
    if body is None:
        # find body
        body = max((rs[:, 2].max(), ls[:, 2].max()))
    li = len(ls) - 1
    ri = len(rs) - 1
    while li > 0:
        if ls[li, 2] > body / 2.:
            break
        li -= 1
    while ri > 0:
        if rs[ri, 2] > body / 2.:
            break
        ri -= 1
    if ls[li, 1] < rs[ri, 1]:
        return lvl, True, 'r'
    return lvl, True, 'l'


def h5(e):
    """>1 animal, >1 left, >1 right"""
    lvl, valid, direction = h4(e)
    if valid:
        return lvl, valid, direction
    lvl = 5
    if len(e['animals']) < 2:
        return lvl, False, None
    # check if first rising edge and last falling edge agree
    ls, rs = e['l'], e['r']
    if ls[0][0] < rs[0][0] and ls[-1][1] < rs[-1][1]:
        return lvl, True, 'r'
    if ls[0][0] > rs[0][0] and ls[-1][1] > rs[-1][1]:
        return lvl, True, 'l'
    # try to split into single events, if so parse them
    # when splitting, is 1 beam break about the sum of the other two
    # if not, parse as 1 event similar to h4
    return lvl, False, None


def apply_heuristics(tube_events):
    for e in tube_events:
        lvl, valid, direction = h5(e)
        if not valid:
            direction = '?'
        e['heuristic'] = {
            'level': lvl, 'valid': valid, 'direction': direction,
        }


def merge_close_reads(reads, threshold=1000):
    # keep cross board reads
    m = numpy.ones(len(reads), dtype='bool')
    m[1:] = numpy.diff(reads[:, 0]) > threshold
    m[1:] |= numpy.diff(reads[:, 1] != 0)
    return reads[m]
