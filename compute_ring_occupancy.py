#!/usr/bin/env python

import sys

import numpy
import pylab

import blockpartyrfid
import blockpartyrfid.oo.colony


dname = '180620'
n_cages = 10
is_ring = True
output_filename = 'ring_occupancy.csv'
reads_output_filename = 'reads.csv'
multi_animal_events_filename = 'multi_animal_events.csv'
min_rfid_reads = 100

if len(sys.argv) > 1:
    dname = sys.argv[1]

# construct a colony
c = blockpartyrfid.oo.colony.Colony(n_cages, ring=is_ring)

c.save_reads = True
c.ignore_animals = [
#    "C000000000", # read errors
#    "007F007F00",
#    "F000000000",
#    "002FBE75C3",
#    "002FBE7443",
#    "002FBE7455",
#    "002FBE744F",
#    "002FBE75D3",
#    "002FBE75F3",
#    "002FBE76F5",  # died
]

# process logs
c.process_directory(dname)

animals = [
    aid for aid in c.animals if c.animals[aid].get_n_reads() > min_rfid_reads]
print(animals)
print("Founds animals:")
for a in animals:
    print("  %s" % a)
print("RFID merge threshold:", c.rfid_merge_threshold)
# save reads
print("Saving to %s" % reads_output_filename)
with open(reads_output_filename, 'w') as f:
    for r in c.saved_reads:
        f.write(','.join([str(s) for s in r]) + '\n')

# get the predicted occupancy
o = c.get_occupancy(animals=animals)

# get chanse matrix
cm, cm_animals = c.get_chase_matrix(animals=animals)

# save occupancy as csv
print("Saving to %s" % output_filename)
numpy.savetxt(output_filename, o, delimiter=',')

# save multi-animal events
# first combine into 1 list
maes = []
for (i, t) in enumerate(c.tubes):
    for e in t.multi_animal_events:
        # time, tube index, chaser, chasee
        maes.append([e[2], i, e[0], e[1]])
# sort by time
maes.sort(key=lambda e: e[0])
# save
with open(multi_animal_events_filename, 'w') as f:
    for mae in maes:
        f.write(','.join([str(s) for s in mae]) + '\n')

# plot
pylab.figure()
blockpartyrfid.vis.plot_time_in_cage(o)
pylab.figure()
blockpartyrfid.vis.plot_occupancy(o[-1000:])
pylab.figure()
blockpartyrfid.vis.plot_chase_matrix(cm, cm_animals)
pylab.show()
