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
def find_shorted_board_to_board_time(df):
    t = numpy.array(df['time'])
    b = numpy.array(df['board'])
    m = b[1:] != b[:-1]
    return (t[1:][m] - t[:-1][m]).min()


grouped_rfid_df = rfid_df.groupby('data0')
rfid_merge_threshold = grouped_rfid_df.apply(
    find_shorted_board_to_board_time).min()

ad = {}
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
    b = numpy.array(ad[aid]['board'])
    
    # find all 'starts' (where board at t0 is 1 off from board at t1)
    # for each start, trace out until next start (or error)
    # if the next start agrees, accept, if not, reject
    # compute reliability score (accepts vs rejects)
    # output occupancy (start time, end time, cage, animal[name], ?)
    # what about unknown period? fill in possible cages?

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