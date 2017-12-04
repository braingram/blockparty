#!/usr/bin/env python

import sys

import numpy
import pylab

from . import consts
from . import db


default_cm = pylab.cm.spring
#if hasattr(pylab.cm, 'viridis'):
#    default_cm = pylab.cm.viridis
#else:
#    default_cm = pylab.cm.winter


def plot_rfid_events(events, timerange=None, ymin=-0.5, ymax=0.5, color='k'):
    rfid = db.sel(events, event='rfid', timerange=timerange)
    if len(rfid) == 0:
        return
    # remove any read errors?
    #rfid = rfid[:, 4] >= 0
    #pylab.vlines(rfid[:, consts.TIME_COLUMN], ymin, ymax, color=color)
    idi = numpy.where(rfid[:, 4] == 0)[0]
    if idi[0] == 0:
        idi = idi[1:]
    if idi[-1] == rfid.shape[0] - 1:
        idi = idi[:-1]
    si = rfid[idi-1]
    ei = rfid[idi+1]
    assert numpy.all(si[:, 3] == 1)
    assert numpy.all(ei[:, 3] == 0)
    n = si.shape[0]
    b = numpy.ones(n) * ymin
    h = numpy.ones(n) * (ymax - ymin)
    w = ei[:, 0] - si[:, 0]
    l = si[:, 0]
    pylab.barh(b, w, h, l, color='pink')

    rfid_y = (ymin + ymax) * 0.5
    for ev in rfid[idi]:
        pylab.text(
            ev[consts.TIME_COLUMN],
            rfid_y, '%s' % ev[consts.RFID_ID_COLUMN],
            color='k')


def plot_beam_events(
        events, side=None, timerange=None, height=1.0, offset=0.0,
        color='b'):
    b = db.sel(events, event='beam', data0=side, timerange=timerange)
    if len(b) == 0:
        return
    pylab.step(
        b[:, consts.TIME_COLUMN],
        b[:, consts.BEAM_STATE_COLUMN] * height + offset,
        where='post', color=color)


def plot_touch_binary_events(
        events, side=None, timerange=None, height=1.0, offset=0.0,
        color='g'):
    b = db.sel(events, event='touch_binary', data0=side, timerange=timerange)
    if len(b) == 0:
        return
    pylab.step(
        b[:, consts.TIME_COLUMN],
        b[:, consts.TOUCH_STATE_COLUMN] * height + offset,
        where='post', color=color)


def plot_touch_raw_events(
        events, side=None, timerange=None, height=1.0, offset=0.0,
        color='g'):
    # TODO
    raise NotImplementedError()
    b = db.sel(events, event='touch_binary', data0=side, timerange=timerange)
    if len(b) == 0:
        return
    pylab.step(
        b[:, consts.TIME_COLUMN],
        b[:, consts.TOUCH_STATE_COLUMN] * height + offset,
        where='post', color=color)


def plot_events(events, timerange=None, event_types=None, offset=0.0):
    # TODO split boards
    bids = db.all_boards(events)
    if len(bids) > 1:
        for (i, bid) in enumerate(bids):
            plot_events(
                db.sel(events, board=bid),
                timerange=timerange, event_types=event_types,
                offset=i * 7)
        return
    if event_types is None:
        #event_types = ['rfid', 'beam', 'touch_binary', 'touch_raw']
        event_types = ['rfid', 'beam', 'touch_binary']
    if not isinstance(event_types, (list, tuple)):
        event_types = [event_types, ]
    # TODO determine offsets
    if 'rfid' in event_types:
        plot_rfid_events(
            events, ymin=offset - 0.5, ymax=offset + 0.5,
            timerange=timerange)
    if 'beam' in event_types:
        plot_beam_events(
            events, side='l', timerange=timerange, offset=offset - 1.5)
        plot_beam_events(
            events, side='r', timerange=timerange, offset=offset + 0.5)
    if 'touch_binary' in event_types:
        plot_touch_binary_events(
            events, side='l', timerange=timerange, offset=offset - 2.5)
        plot_touch_binary_events(
            events, side='r', timerange=timerange, offset=offset + 1.5)


def plot_time_in_cage(
        occupancy, animals=None, n_cages=None, full_time=None, cm=None):
    if animals is None:
        aids = numpy.unique(occupancy[:, 3])
        aids.sort()
    else:
        aids = animals
    if n_cages is None:
        n_cages = numpy.max(occupancy[:, 2]) + 1
    
    if full_time is None:
        full_time = occupancy[-1, 1] - occupancy[0, 0]
    blabels = [str(cid) for cid in range(n_cages)]
    blabels.append('?')
    # TODO set figure size
    if cm is None:
        cm = default_cm
    spb = 101 + len(aids) * 10
    colors = [cm(bid / float(n_cages - 1)) for bid in range(n_cages)]
    colors.append((0., 0., 0., 0.0))  # add white for unknown
    for (i, aid) in enumerate(aids):
        ao = occupancy[occupancy[:, 3] == aid]
        cts = []
        for ci in range(n_cages):
            cts.append(db.sum_range(ao[ao[:, 2] == ci, :2]))
        # add un-accounted for time
        cts.append(full_time - sum(cts))
        pylab.subplot(spb + i)
        pylab.pie(
            cts, labels=blabels, autopct='%1.1f%%', colors=colors)
        pylab.title(aid)


def plot_occupancy(
        occupancy, offset=0.0, cm=None, n_cages=None, n_animals=None,
        label_left=None):
    if cm is None:
        cm = default_cm
    # [enter, exit, cage, animal]

    # get all animals
    aids = numpy.unique(occupancy[:, 3])
    aids.sort()
    if n_animals is None:
        n_aids = len(aids)
    else:
        n_aids = n_animals



    # find # of cages
    if n_cages is None:
        n_cages = len(numpy.unique(occupancy[:, 2]))
    # give each cage a color
    colors = {
        cid: cm(cid / float(n_cages - 1.0)) for cid
        in numpy.arange(n_cages)}

    bar_height = 1. / n_aids
    # plot each animal
    for (i, aid) in enumerate(aids):
        # get occupancy for this animal
        ao = occupancy[occupancy[:, 3] == aid]
        
        # add label
        ty = i * bar_height + offset
        tx = ao[0, 0] if label_left is None else label_left
        pylab.text(tx, ty, str(aid), ha='right', va='center', color='k')
        
        # barh(bottom, width, height, left, **kwargs)
        cs = [colors[b] for b in ao[:, 2]]
        l = numpy.ones_like(ao[:, 1] - ao[:, 0]) * i * bar_height + offset
        pylab.barh(
            l, ao[:, 1] - ao[:, 0],
            bar_height, ao[:, 0], color=cs)

    yl = pylab.ylim()
    ylmin = min(yl[0], offset)
    ylmax = max(yl[1], 1 + offset)
    if yl != (ylmin, ylmax):
        pylab.ylim(ylmin, ylmax)


def plot_occupancy2(occupancy, offset=0.0, cm=None, n_cages=None, n_animals=None):
    if cm is None:
        if hasattr(pylab.cm, 'viridis'):
            cm = pylab.cm.viridis
        else:
            cm = pylab.cm.winter
    # [enter, exit, cage, animal]

    # give each animal a color
    aids = numpy.unique(occupancy[:, 3])
    aids.sort()
    if n_animals is None:
        n_aids = len(aids)
    else:
        n_aids = n_animals
    colors = {
        aid: cm(v) for (aid, v)
        in zip(aids, numpy.linspace(0., 1., n_aids))}

    # find # of cages
    if n_cages is None:
        n_cages = len(numpy.unique(occupancy[:, 2]))

    bar_height = 1. / n_aids
    # plot each animal
    for (i, aid) in enumerate(aids):
        # get occupancy for this animal
        ao = occupancy[occupancy[:, 3] == aid]

        # barh(bottom, width, height, left, **kwargs)
        pylab.barh(
            ao[:, 2] + i * bar_height + offset, ao[:, 1] - ao[:, 0],
            bar_height, ao[:, 0], color=colors[aid])

    # draw cage dividers
    for i in range(n_cages + 1):
        pylab.axhline(i + offset, color='k')
    yl = pylab.ylim()
    ylmin = min(yl[0], offset)
    ylmax = max(yl[1], n_cages + offset)
    if yl != (ylmin, ylmax):
        pylab.ylim(ylmin, ylmax)


def old_plot_events(rfid, lb, rb, td=None, timerange=None):
    if timerange is not None:
        rfid = sel(rfid, timerange=timerange)
        lb = sel(lb, timerange=timerange)
        rb = sel(rb, timerange=timerange)
        if td is not None:
            td = sel(td, timerange=timerange)
    if td is not None:
        tl = td[:, 3]
        tr = td[:, 4]
        if (
                (abs(tl.max() - 1.0) < 1E-9) and
                (abs(tr.max() - 1.0) < 1E-9) and
                (abs(tl.min()) < 1E-9) and
                (abs(tr.min()) < 1E-9)):
            # assume this is binarized data
            pylab.step(td[:, 0], tl * 0.5 + 0.25, where='post', color='b')
            pylab.step(td[:, 0], tr * 0.5 + 2.25, where='post', color='r')
        else:
            tl = (tl - tl.min()) / float(tl.ptp())
            tr = (tr - tr.min()) / float(tr.ptp())
            pylab.plot(td[:, 0], tl * 0.5 + 0.25, color='b')
            pylab.plot(td[:, 0], tr * 0.5 + 2.25, color='r')
        pylab.step(lb[:, 0], lb[:, 4] * 0.5 + 1.25, where='post', color='b')
        pylab.step(rb[:, 0], rb[:, 4] * 0.5 + 3.25, where='post', color='r')
        pylab.vlines(rfid[:, 0], 0, 4, color='k')
        rfid_y = 2
    else:
        pylab.step(lb[:, 0], lb[:, 4] * 0.5 + 0.25, where='post', color='b')
        pylab.step(rb[:, 0], rb[:, 4] * 0.5 + 1.25, where='post', color='r')
        pylab.vlines(rfid[:, 0], 0, 2, color='k')
        rfid_y = 1
    for ev in rfid:
        c = {
            -1: 'blue',
            0: 'black',
            1: 'red'}[ev[4]]  # [dirs[i]]
        pylab.text(ev[0], rfid_y, '%s' % ev[3], color=c)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        log_dir = sys.argv[1]
    show_all = True
    if len(sys.argv) > 2:
        show_all = sys.argv[2].lower()[0] == 't'
    data = load_log_directory(log_dir)
    tdata = load_log_directory(log_dir, touch=True)

    # just do board 0 for now, and first hour
    # 23 - 25 has data for ~2 hours of ok looking data for both boards
    kwargs = {
        'board': 1,
    }
    #kwargs = {
    #    'board': 1, 'timerange': (
    #        data[0, 0] + 24 * 3600000,
    #        data[0, 0] + 32 * 3600000)}
    data = sel(data, **kwargs)
    tdata = sel(tdata, **kwargs)
    tlt = tdata[:, 3].ptp() * 0.75 + tdata[:, 3].min()
    trt = tdata[:, 4].ptp() * 0.75 + tdata[:, 4].min()
    tdb = tdata.copy()
    # apply threshold
    tdb[:, 3] = tdb[:, 3] > tlt
    tdb[:, 4] = tdb[:, 4] > trt
    # find only transitions
    m = numpy.abs(numpy.diff(tdb, axis=0))
    m = numpy.logical_or(m[:, 3], m[:, 4])
    mtdb = tdb[1:][m]
    # split left/right touch events
    lt = mtdb.copy()
    rt = mtdb.copy()
    lt[:, 3] = 0
    rt[:, 3] = 1
    lt[:, 4] = mtdb[:, 3]
    rt[:, 4] = mtdb[:, 4]
    #d = sel(d, board=0)

    # plot events
    rfid = sel(data, event=0, data1=0)
    lb = sel(data, event=1, data0=0)
    rb = sel(data, event=1, data0=1)
    lbb = sel(lb, data1=1)
    rbb = sel(rb, data1=1)
    plot_events(rfid, lb, rb, mtdb)
    pylab.show()

    # find events with correct durations
    vlb = select_events_by_duration(lb, 100, 5000)
    vrb = select_events_by_duration(rb, 100, 5000)
    vlt = select_events_by_duration(lt, 100, 5000)
    vrt = select_events_by_duration(rt, 100, 5000)
    
    #pylab.figure()
    pylab.vlines(rfid[:,0], -1, 1, color='r')
    pylab.vlines(vlb[:,0], 1, 2, color='b')
    pylab.vlines(vlt[:,0], 2, 3, color='g')
    pylab.vlines(vrb[:,0], -2, -1, color='c')
    pylab.vlines(vrt[:,0], -3, -2, color='m')
    pylab.show()
    
    # assign other events to rfid events
    events = []
    for ev in rfid:
        t = ev[0]
        event = {
            't': t,
            'bid': ev[1],
            'aid': ev[3],
            'lbe': closest_event(vlb, t, 1000),
            'rbe': closest_event(vrb, t, 1000),
            'lte': closest_event(vlt, t, 1000),
            'rte': closest_event(vrt, t, 1000),
        }
        # compute dts of other events
        dts = [None, None, None, None]
        for (i, k) in enumerate(('lbe', 'rbe', 'lte', 'rte')):
            if event[k] is not None:
                dts[i] = event[k][0] - t
        event['dts'] = dts
        events.append(event)
    
    """
    # attempt to assign directions to rfid reads
    # heuristic 1: check if a beam is broken, if so, direction is opposite beam
    print("applying heuristic 1")
    for ev in rfid:
        d = 0
        #l = sel(lb, timerange=(0, ev[0]))[::-1]
        l = sel(lb, timerange=(ev[0]-600000, ev[0]))[::-1]
        if len(l):
            l = l[0]
        else:
            continue  # skip
        #r = sel(rb, timerange=(0, ev[0]))[::-1]
        r = sel(rb, timerange=(ev[1]-600000, ev[0]))[::-1]
        if len(r):
            r = r[0]
        else:
            continue  # skip
        if l[4] == 1:  # left is broken
            if r[4] == 1:  # right is also broken
                # which broke first
                if l[0] < r[0]:  # right
                    d = 1
                else:  # left
                    d = -1
            else:  # right
                d = 1
        elif r[4] == 1:
            d = -1
        if d != 0:
            ev[4] = d

    # heuristic 2: if a beam breaks within t seconds, direction is opposite
    print("applying heuristic 2")
    for ev in rfid:
        if ev[4] != 0:
            continue
        d = 0
        l = sel(lbb, timerange=(ev[0], ev[0] + 5000))
        r = sel(rbb, timerange=(ev[0], ev[0] + 5000))
        if not len(l) and not len(r):
            continue
        if not len(r):  # right
            d = 1
        elif not len(l):  # left
            d = -1
        elif l[0][0] < r[0][0]:  # right
            d = 1
        else:  # left
            d = -1
        if d != 0:
            ev[4] = d

    unclassified = rfid[rfid[:, 4] == 0]
    print("%s unclassified reads" % len(unclassified))

    # TODO look for conflicts
    conflicts = []
    animals = list(set(rfid[:, 3]))
    for aid in animals:
        r = rfid[(rfid[:, 3] == aid) & (rfid[:, 4] != 0)]
        d = numpy.abs(numpy.diff(r[:, 4]))
        cevs = r[:-1][d != 2]
        inds = numpy.where(d != 2)[0]
        if len(inds):
            for i in inds:
                conflicts.append((r[i], r[i + 1]))
        n = numpy.count_nonzero(d != 2)
        print("%i[%0.2f] conflicts for %s" % (n, n * 100. / len(d), aid))

    if show_all:
        for ev in unclassified:
            pylab.suptitle("unclassified[%s]" % ((ev[0], ev[1], ev[3], ev[4]), ))
            plot_events(rfid, lb, rb, timerange=(ev[0] - 60000, ev[0] + 60000))
            pylab.show()

        for (a, b) in conflicts:
            pylab.figure(1)
            pylab.suptitle("conflict[%s]" % ((a[0], a[1], a[3], a[4]), ))
            plot_events(rfid, lb, rb, timerange=(a[0] - 60000, a[0] + 60000))
            pylab.axvline(a[0], color='g')
            pylab.figure(2)
            pylab.suptitle("conflict[%s]" % ((b[0], b[1], b[3], b[4]), ))
            plot_events(rfid, lb, rb, timerange=(b[0] - 60000, b[0] + 60000))
            pylab.axvline(b[0], color='g')
            pylab.show()
    #pylab.show()
    """
