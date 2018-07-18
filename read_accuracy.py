#!/usr/bin/env python

import sys

import numpy
import pylab

import blockpartyrfid

dname = 'BP_TEST2_sparkTags_180601_155416'
board = 0

if len(sys.argv) > 1:
    dname = sys.argv[1]

if len(sys.argv) > 2:
    board = int(sys.argv[2])

# load in all data
if 'd' not in locals():
    d = blockpartyrfid.io.load_log_directory(dname, convert_times=False)

bd = blockpartyrfid.db.sel(d, board=board)

lbb = blockpartyrfid.db.sel(bd, event='beam', data0=0)[:, 0]
rbb = blockpartyrfid.db.sel(bd, event='beam', data0=1)[:, 0]
lbbt = lbb[::2]
rbbt = rbb[::2]
# ignore animal for now
rd = blockpartyrfid.db.sel(bd, event='rfid', data1=0)
rdt = rd[:, 0]

# filter beam breaks
def filter_bbs(bbs):
    bs = []
    b = None
    for (r, f) in zip(bbs[::2], bbs[1::2]):
        if b is None:
            b = (r, f)
        else:
            # check if rising edge is further than duration
            bbd = f - r
            # compute duration of previous beam break and clip to range = d
            d = min(max(200, (b[1] - b[0])), 1000)
            # if rising edge of this beam bream is > d away and it's duration
            # is > some min duration, accept as new beam break
            if r > (b[1] + d) and bbd > 50:
                bs.append(b)
                b = (r, f)
            else:  # else eat next beam break
                b = (b[0], f)
    bs.append(b)
    return numpy.array(bs)

lbbs = filter_bbs(lbb)
rbbs = filter_bbs(rbb)

rs = []
rr = [rd[0,0], rd[0,3]]
last = rd[0]
for r in rd:
    # different animal or later read
    if r[3] != last[3] or r[0] - last[0] > 500:
        rs.append(rr)  # TODO, save end time?
        rr = [r[0], r[3]]
    last = r
rs.append(rr)
rs = numpy.array(rs)
        
# for each lbb/rbb/r, find the closest rbb,lbb,r
pairs = {'rfid': [], 'left': [], 'right': []}
for i in range(len(rs)):
    t = rs[i][0]
    li = numpy.abs(lbbs[:,0] - t).argmin()
    ri = numpy.abs(rbbs[:,0] - t).argmin()
    pairs['rfid'].append([i, li, ri])

for i in range(len(lbbs)):
    t = lbbs[i][0]
    ii = numpy.abs(rs[:,0] - t).argmin()
    ri = numpy.abs(rbbs[:,0] - t).argmin()
    pairs['left'].append([ii, i, ri])

for i in range(len(rbbs)):
    t = rbbs[i][0]
    ii = numpy.abs(rs[:,0] - t).argmin()
    li = numpy.abs(lbbs[:,0] - t).argmin()
    pairs['right'].append([ii, li, i])


# if the closest pairs match using lbb,rbb,and r as ref, accept as complete
complete = []
missing = []
for k in pairs:
    for i in pairs[k]:
        mks = []
        for k2 in pairs:
            if k2 == k:
                continue
            if i not in pairs[k2]:
                mks.append(k2)
        if len(mks):
            missing.append([k, i, mks])
        else:
            complete.append([k, i, []])

print(
    "percent incomplete events:",
    len(missing) * 100. / (len(missing) + len(complete)))
mrs = [
    m for m in missing
    if m[0] != 'rfid' and len(m[2]) == 1 and m[2][0] == 'rfid']
print("percent missed reads:", len(mrs) * 100. / (len(missing) + len(complete)))

fd = {'rfid': rs, 'left': lbbs, 'right': rbbs}
blockpartyrfid.vis.plot_events(bd)
print("Enter any key to exit, press mouse button to advance")

def show_event(event, wait=True):
    k, i, mks = event
    # i = [id, left, right]
    ie = fd['rfid'][i[0]]
    le = fd['left'][i[1]]
    re = fd['right'][i[2]]
    xmin = min([ie[0], le[0], re[0]])
    xmax = max([ie[0], le[1], re[1]])
    pylab.xlim([xmin - 10000, xmax + 10000])
    # mark rfid & beam breaks
    pylab.axvspan(le[0], le[1], color='b', alpha=0.1)
    pylab.axvspan(re[0], re[1], color='b', alpha=0.1)
    pylab.scatter(ie[0], 0, color='r')
    if len(mks) == 0:  # complete event
        pylab.title("complete")
    else:
        pylab.title("missing: %s" % (mks, ))
    if wait:
        pylab.gcf().canvas.draw()
        try:
            r = pylab.waitforbuttonpress(timeout=-1)
        except KeyboardInterrupt:
            r = True
        return r

"""
for c in complete:
    if show_event(c):
        break
"""

for mr in mrs:
    if show_event(mr):
        break
"""
n = len(mrs)
for (index, mr) in enumerate(mrs):
    show_event(mr)
    pylab.gcf().canvas.draw()
    try:
        r = pylab.waitforbuttonpress(timeout=-1)
    except KeyboardInterrupt:
        r = True
    if r:  # key was pressed
        break
"""
"""
for t in rdt:
    l = lbbt[numpy.abs(lbbt - t).argmin()]
    r = rbbt[numpy.abs(rbbt - t).argmin()]
    #i = rdt[numpy.abs(rdt - t).argmin()]
    i = t
    pairs.append((l, r, i))

# for each rbb, find the closest?

pairs = numpy.array(pairs)
nbins = int(len(pairs) ** 0.5)
il = pairs[:,2] - pairs[:,0]
ir = pairs[:,2] - pairs[:,1]

pylab.figure()
_, bins, _ = pylab.hist(il, bins=nbins)
pylab.hist(ir, bins=bins)
pylab.title("to rfid time")
pylab.figure()
pylab.scatter(il, ir, s=3, alpha=0.5)
pylab.xlabel("id to left time")
pylab.ylabel("id to right time")
pylab.gca().set_aspect(1.0)
pylab.show()
"""