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
min_rfid_reads = 100

if len(sys.argv) > 1:
    dname = sys.argv[1]

# construct a colony
c = blockpartyrfid.oo.colony.Colony(n_cages, ring=is_ring)

# process logs
c.process_directory(dname)

animals = [
    aid for aid in c.animals if c.animals[aid].get_n_reads() > min_rfid_reads]

# get the predicted occupancy
o = c.get_occupancy(animals=animals)

# get chanse matrix
cm, cm_animals = c.get_chase_matrix(animals=animals)

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
