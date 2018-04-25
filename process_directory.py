#!/usr/bin/env python

import datetime
import glob
import os
import pickle
import time

import numpy
import pandas
import scipy.ndimage


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
# ensure all tags are upper case
animals['rfid'] = [s.upper() for s in animals['rfid']]

# add datetime column, maybe do this after merging etc...
fets = numpy.array(fets)
slope, intercept = numpy.polyfit(fets[:, 1], fets[:, 0], 1)
rfid_df['datetime'] = pandas.to_datetime(
    ((
        numpy.array(rfid_df['time'], dtype='f8') * slope + intercept
        ) * 1000).astype('int64'),
    unit='ms')

# add name column, maybe do this after merging etc...
aid_to_name_map = {i.rfid: i.name for i in animals.itertuples()}
rfid_df['name'] = rfid_df['data0'].replace(aid_to_name_map)

# TODO merge close rfid reads    
def find_shortest_board_to_board_time(df):
    t = numpy.array(df['time'])
    b = numpy.array(df['board'])
    m = b[1:] != b[:-1]
    return (t[1:][m] - t[:-1][m]).min()


grouped_rfid_df = rfid_df.groupby('data0')
rfid_merge_threshold = grouped_rfid_df.apply(
    find_shortest_board_to_board_time).min()

animal_data = {}
animal_occupancies = {}
for aid in grouped_rfid_df.groups:
    df = grouped_rfid_df.get_group(aid)
    # keep all events where dt > thresh or board changed
    t = numpy.array(df['time'])
    b = numpy.array(df['board'])
    m = numpy.ones_like(t, dtype='bool')
    m[1:] = (t[1:] - t[:-1]) > rfid_merge_threshold
    m[1:] |= b[1:] != b[:-1]
    
    animal_data[aid] = df[m]
    
    # TODO convert from reads to sequence to occupancy
    df = animal_data[aid]
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

# merge animal occupancies: start_datetime, end_datetime, cage, animal_id, animal_name
occupancy = None
for aid in animal_occupancies:
    df = pandas.DataFrame(
        animal_occupancies[aid]['sequence'],
        columns=['start_time', 'end_time', 'cage'])
    df['rfid'] = aid
    df['name'] = aid_to_name_map[aid]
    if occupancy is None:
        occupancy = df
    else:
        occupancy = pandas.concat((occupancy, df), ignore_index=True)
occupancy = occupancy.sort_values('start_time').reset_index(drop=True)
# add start_date, end_date
occupancy['start_date'] = pandas.to_datetime(
    ((
        numpy.array(occupancy['start_time'], dtype='f8') * slope + intercept
        ) * 1000).astype('int64'),
    unit='ms')
occupancy['end_date'] = pandas.to_datetime(
    ((
        numpy.array(occupancy['end_time'], dtype='f8') * slope + intercept
        ) * 1000).astype('int64'),
    unit='ms')

# find multi-animal events
# generate rfid_reads dataframe
filtered_rfid_df = pandas.concat(animal_data.values()).sort_values('time')

# re-group animal events by board
by_board_rfid_df = filtered_rfid_df.groupby('board')
by_board_groups = {
    g: by_board_rfid_df.get_group(g) for g in by_board_rfid_df.groups}

# use rfid merge threshold as multi-animal event threshold
mae_threshold = rfid_merge_threshold
maes = []
for b in by_board_groups:
    df = by_board_groups[b]
    dt = numpy.diff(numpy.array(df['time']))
    ls, nl = scipy.ndimage.label(dt < mae_threshold)
    for l in xrange(1, nl + 1):
        inds = numpy.where(ls == l)[0]
        s = inds.min()
        e = inds.max() + 2
        maes.append(df.iloc[s:e])

# generate chase matrix
names = list(animals['name'])
n_animals = len(names)
chase_matrix = numpy.zeros((n_animals, n_animals), dtype='int')
for mae in maes:
    chaser = mae.iloc[-1]['name']
    chaser_index = names.index(chaser)
    for chased in mae.iloc[:-1]['name']:
        chased_index = names.index(chased)
        chase_matrix[chaser_index, chased_index] += 1
chase_matrix = pandas.DataFrame(chase_matrix, index=names, columns=names)
        
# save results
filtered_rfid_df.to_csv('filtered_rfid.csv')
occupancy.to_csv('occupancy.csv')
chase_matrix.to_csv('chase_matrix.csv')
with open('multi_animal_events.p', 'wb') as f:
    pickle.dump(maes, f)

# TODO plot

# print out some info
print()
print("=========== Session info ============")
print("Duration of experiment: %s" % rfid_df['datetime'].ptp())
print()
ec = rfid_df['data1'].value_counts()
print("RFID read errors: %s" % (ec.get('1', '0')))
#print("Raw animal tags and reads:")
#print(rfid_df['name'].value_counts())
print("Filtered animal tags and reads:")
print(filtered_rfid_df['name'].value_counts())
print("")
print("Multi-animal events: %s" % len(maes))
print("Number of doubles, triples, etc...")
cs = pandas.Series([len(i) for i in maes])
print(cs.value_counts())
print("")
