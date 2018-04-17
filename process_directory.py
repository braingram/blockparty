#!/usr/bin/env python

import datetime
import glob
import os
import time

import numpy
import pandas


dname = '180131'

print("Processing directory: %s" % dname)
# get all data filenames (don't include touch data)
fns = sorted([
    fn for fn in glob.glob(os.path.join(dname, '*_*.csv'))
    if ('touch' not in fn) and (os.path.getsize(fn) != 0)])
print("Found %s log files" % len(fns))

dfs = []
fets = []
for fn in fns:
    df = pandas.read_csv(fn, names=['time', 'board', 'event_type', 'data0', 'data1'])
    t = numpy.array(df['time'])
    if not numpy.all(t[1:] >= t[:-1]):
        # if df['time'] is not ascending, teensy time rolled over
        raise NotImplementedError("Teensy time rolled over")
    dt = time.mktime(datetime.datetime.strptime(
        os.path.splitext(os.path.basename(fn))[0],
        '%y%m%d_%H%M%S').timetuple())
    ft = df['time'][0]
    fets.append((dt, ft))
    dfs.append(df)
event_df = pandas.concat(dfs)

# select all rfid events
rfid_df = event_df[(event_df['event_type'] == 0) & (~event_df['data0'].isin(('r', 'f')))].copy()

# read in animal meta data (if available)
afn = os.path.join(dname, 'animals.csv')
if os.path.exists(afn):
    animals = pandas.read_csv(afn)
    print("Found animal meta data:")
    print(animals)
    # remove all animals not in animals.csv
    rfid_df = rfid_df[rfid_df['data0'].isin(animals['rfid'])]
else:
    # necessary columns 'rfid'
    tags = rfid_df['data0'].unique()
    animals = pandas.DataFrame({
        'rfid': tags,
        'name': tags,
    })


# add datetime column, TODO do this after merging etc...
fets = numpy.array(fets)
slope, intercept = numpy.polyfit(fets[:, 1], fets[:, 0], 1)
rfid_df['datetime'] = pandas.to_datetime(
    ((
        numpy.array(rfid_df['time'], dtype='f8') * slope + intercept
        ) * 1000).astype('int64'),
    unit='ms')

# add name column, TODO do this after merging etc...
rfid_df['name'] = rfid_df['data0'].replace(
    {i.rfid: i.name for i in animals.itertuples()})

# TODO merge close rfid reads    
def find_shortest_board_to_board_time(df):
    t = numpy.array(df['time'])
    b = numpy.array(df['board'])
    m = b[1:] != b[:-1]
    return (t[1:][m] - t[:-1][m]).min()


grouped_rfid_df = rfid_df.groupby('data0')
rfid_merge_threshold = grouped_rfid_df.apply(
    find_shortest_board_to_board_time).min()

ad = {}
animal_occupancies = {}
for aid in grouped_rfid_df.groups:
    df = grouped_rfid_df.get_group(aid)
    # keep all events where dt > thresh or board changed
    t = numpy.array(df['time'])
    b = numpy.array(df['board'])
    m = numpy.ones_like(t, dtype='bool')
    m[1:] = (t[1:] - t[:-1]) > rfid_merge_threshold
    m[1:] |= b[1:] != b[:-1]
    
    ad[aid] = df[m]
    
    # TODO convert from reads to sequence to occupancy
    df = ad[aid]
    t = numpy.array(df['time'])
    b = numpy.array(df['board'])
    
    # find all 'starts' (where board at t0 is 1 off from board at t1)
    starts = numpy.where(numpy.abs(numpy.diff(b)) == 1)[0]
    starts_cage = numpy.vstack((b[starts], b[starts + 1])).max(axis=0)
    # find all 'misses' where board changes by >1
    misses = numpy.where(numpy.abs(numpy.diff(b)) > 1)[0]
    
    occupancy = []
    successes = []
    failures = []
    n = len(b)
    ns = 0
    # for each start index
    for (si, s) in enumerate(starts[:-1]):
        # this is only accepting forward sequences (which are verified)
        # this is not accepting backward sequences when the forward is verified
        seq = []
        # determine cage from board sequence
        cage = starts_cage[si]
        # at df[s]['time'] animal entered cage
        i = s + 1
        while i < n:
            # trace out until next start (or error)
            if i in misses:
                # lost sequence, stop here, reject
                failures.append((s, i, 1))
                break
            # if the next start agrees, accept, if not, reject
            #if (starts[i] not in (cage, cage - 1)
            seq.append([t[i-1], t[i], cage])
            if b[i] == cage:
                # moved up 1 cage
                cage += 1
            elif b[i] == cage - 1:
                # moved down 1 cage
                cage -= 1
            else:  # error!
                failures.append((s, i, 2))
                break
            if i == starts[si + 1]:
                if cage == starts_cage[si + 1]:
                    ns += 1
                    successes.append((s, i, 0))
                    # build occupancy from
                    # df[s] entered start_cage
                    # df[i] left current cage
                    occupancy.extend(seq)
                else:
                    failures.append((s, i, 3))
                break
            i += 1
    # compute reliability score (accepts vs rejects)
    # output occupancy (start time, end time, cage, animal[name], ?)
    animal_occupancies[aid] = {
        'sequence': occupancy,
        'reliability': ns / float(len(starts)),
    }
    # TODO what about unknown period? fill in possible cages?

# TODO find multi-animal events
# TODO generate chase matrix
# TODO save, plot, print
    
# print out some info
print()
print("=========== Session info ============")
print("Duration of experiment: %s" % rfid_df['datetime'].ptp())
print()
ec = rfid_df['data1'].value_counts()
print("RFID read errors: %s" % (ec.get('1', '0')))
print("Raw animal tags and reads:")
print(rfid_df['name'].value_counts())