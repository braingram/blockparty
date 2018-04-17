#!/usr/bin/env python

import sys

import numpy
import pylab

import blockpartyrfid

females = [
    0x2a006d2c35,
    0x2a006d2e25,
    0x2a006d3160,
    0x2a006d5ca5,
]

dname = '180131'
rfid_merge_threshold = None
output_filename = 'occupancy.csv'
min_rfid_reads = 100

if len(sys.argv) > 1:
    dname = sys.argv[1]

if len(sys.argv) > 2:
    rfid_merge_threshold = int(rfid_merge_threshold)

# load in all data
d = blockpartyrfid.io.load_log_directory(dname, convert_times=False)

# filter to just valid rfid tag events
rd = blockpartyrfid.db.sel(d, event='rfid', data1=0)

# split data by animal
ad = blockpartyrfid.db.split_events(
    rd, board=False, event=False, data0=True, data1=False)

# get all animal ids
print("Founds animals:")
for a in list(ad.keys())[:]:
    if len(ad[a]) < min_rfid_reads:
        del ad[a]
        continue
    print("  %s: %s" % (hex(a), len(ad[a])))
animals = list(ad.keys())
animals = sorted(animals, key=lambda i: 1 - int(i in females))

# as a rfid tag in front of the reader will result in multiple reads
# determine rfid tag read merge threshold
if rfid_merge_threshold is None:
    rfid_merge_threshold = numpy.inf
    for a in animals:
        # find dt for sequential tag reads from 2 different tubes
        cbinds = numpy.where(numpy.diff(ad[a][:, 1]) != 0)[0]
        cbdt = ad[a][cbinds + 1, 0] - ad[a][cbinds, 0]

        # find dt for sequential tag reads from same board
        #wbdt = numpy.diff(ad[a][:-1][numpy.diff(ad[a][:, 1]) == 0, 0])

        rfid_merge_threshold = min(rfid_merge_threshold, cbdt.min())
print("Using rfid_merge_threshold: %s" % rfid_merge_threshold)

rfid_reads = {}
raw_sequences = {}
sequences = {}
occupancy = {}
for a in animals:
    # merge close rfid reads
    rfid_reads[a] = blockpartyrfid.db.merge_close_reads(
        ad[a], rfid_merge_threshold)

    # compute tube sequences
    raw_sequences[a] = blockpartyrfid.occupancy.from_tube_sequence(
        rfid_reads[a])

    # merge to a single sequence
    sequences[a] = blockpartyrfid.occupancy.merge_sequences(raw_sequences[a])

    # convert sequence to occupancy
    occupancy[a] = blockpartyrfid.occupancy.merged_sequence_to_occupancy(
        sequences[a][0], rfid_reads[a])

# merge occupancies from all animals
o = blockpartyrfid.occupancy.merge_occupancies(occupancy.values())

maes = blockpartyrfid.occupancy.find_multi_animal_events(rfid_reads, rfid_merge_threshold)
cm, cm_animals = blockpartyrfid.occupancy.generate_chase_matrix(maes, animals=animals)

# save occupancy as csv
print("Saving to %s" % output_filename)
numpy.savetxt(output_filename, o, delimiter=',')

# plot
pylab.figure()
blockpartyrfid.vis.plot_time_in_cage(o)
pylab.figure()
blockpartyrfid.vis.plot_occupancy(o[-1000:])
pylab.figure()
blockpartyrfid.vis.plot_chase_matrix(cm, cm_animals)
pylab.show()
