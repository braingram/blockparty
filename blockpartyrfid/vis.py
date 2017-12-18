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


def plot_rfid_events(
        events, timerange=None, ymin=-0.5, ymax=0.5, color='k',
        label=False, animals=None):
    rfid = db.sel(events, event='rfid', timerange=timerange, data1=0)
    if len(rfid) == 0:
        return
    if animals is None:
        animals = numpy.unique(rfid[:, consts.DATA0_COLUMN])
    na = animals.size
    cs = numpy.arange(na) / (na - 1.)
    for (a, c) in zip(animals, cs):
        c = pylab.cm.jet(c)
        ae = db.sel(rfid, data0=a)
        if len(ae) == 0:
            continue
        pylab.vlines(ae[:, consts.TIME_COLUMN], ymin, ymax, color=c)
    return
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
    if not label:
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


def plot_events(
        events, timerange=None, event_types=None, offset=0.0, animals=None):
    # TODO split boards
    bids = db.all_boards(events)
    if len(bids) > 1:
        aids = db.all_animals(events)
        for (i, bid) in enumerate(bids):
            plot_events(
                db.sel(events, board=bid),
                timerange=timerange, event_types=event_types,
                offset=i * 7, animals=aids)
        return
    if animals is None:
        animals = db.all_animals(events)
    if event_types is None:
        #event_types = ['rfid', 'beam', 'touch_binary', 'touch_raw']
        event_types = ['rfid', 'beam', 'touch_binary']
    if not isinstance(event_types, (list, tuple)):
        event_types = [event_types, ]
    # TODO determine offsets
    if 'rfid' in event_types:
        plot_rfid_events(
            events, ymin=offset - 0.5, ymax=offset + 0.5,
            timerange=timerange, animals=animals)
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


def plot_occupancy2(
        occupancy, offset=0.0, cm=None, n_cages=None, n_animals=None):
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


def plot_tube_event(e, evs=None, margin=None, offset=0.0):
    pylab.title(
        "%s direction, %s animals" % (e['direction'], len(e['animals'])))
    pylab.barh(
        numpy.ones(len(e['l'])) * -1.5 + offset,
        e['l'][:, 2], 1.0, e['l'][:, 0], color='b', alpha=0.5)
    pylab.barh(
        numpy.ones(len(e['r'])) * 0.5 + offset,
        e['r'][:, 2], 1.0, e['r'][:, 0], color='b', alpha=0.5)
    na = max(2, len(e['animals']))
    for (i, a) in enumerate(e['animals']):
        c = pylab.cm.jet(i / (na - 1.))
        pylab.vlines(
            e['i'][e['i'][:, 3] == a, 0], -0.5, 0.5,
            color=c, linewidth=3)
        ft = e['i'][e['i'][:, 3] == a, 0][0]
        pylab.text(ft + 10, 0.5, str(a), rotation=90, color=c)
    for l in e['l']:
        pylab.text(l[0], -1 + offset, str(l[2]))
    for r in e['r']:
        pylab.text(r[0], 1 + offset, str(r[2]))
    if evs is not None:
        if margin is None:
            margin = [10000, 10000]
        plot_events(
            evs, timerange=[e['start'] - margin[0], e['end'] + margin[1]],
            offset=offset)
    pylab.axvline(e['start'], color='k')
    pylab.axvline(e['end'], color='k')
    yl = pylab.ylim()
    if yl[1] - yl[0] == 3:
        pylab.ylim(yl[0] - 0.5, yl[1] + 0.5)
    # show images
    if 'ims' in e and len(e['ims']) != 0:
        bf = pylab.gcf()
        # draw markers for each image
        ts = sorted(e['ims'].keys())
        ax = pylab.gca()
        sc = pylab.scatter(
            ts, numpy.ones(len(ts)) * 1.5,
            s=200, color='k', picker=5)

        nf = pylab.figure()
        fn = e['ims'][ts[0]]
        im_obj = pylab.imshow(pylab.imread(fn))
        pylab.title(fn)
        im_obj.last_i = 0
        # when hover over marker, update image

        def on_motion(event):
            if event.inaxes != ax:
                return
            cont, ind = sc.contains(event)
            if not cont:
                return
            i = ind['ind'][0]
            if i != im_obj.last_i:
                fn = e['ims'][ts[i]]
                im_obj.set_data(pylab.imread(e['ims'][ts[i]]))
                im_obj.last_i = i
                pylab.title(fn)
                nf.canvas.draw()

        def on_keypress(event):
            if event.key == 'q':
                pylab.close(bf)
                pylab.close(nf)

        bf.canvas.mpl_connect('motion_notify_event', on_motion)
        bf.canvas.mpl_connect('key_press_event', on_keypress)
        nf.canvas.mpl_connect('key_press_event', on_keypress)
