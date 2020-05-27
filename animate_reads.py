
import numpy
import pylab

import matplotlib
import matplotlib.animation


fn = 'reads.csv'
ring = True
n_tubes = None  # None: guess from data 

# read in reads
# how many tubes?
# ring?

class ReadList(object):
    def __init__(self, data):
        self.data = data
        self.n = len(self.data)
        self.i = 0
    
    def get(self):
        if self.i < self.n:
            return self.data[self.i]
        return None
    
    def peek(self):
        i = self.i + 1
        if i < self.n:
            return self.data[i]
        return None

    def advance(self):
        self.i += 1


class DataSource(object):
    def __init__(self, fn, ring=True, n_tubes=None):
        self.n_tubes = 0
        self.min_time = None
        self.data = {}  # by animal id: (timestamp offset, tube id)
        # read in data
        with open(fn, 'r') as f:
            for l in f:
                if not len(l.strip()):
                    continue
                ts, aid, tid = l.strip().split(',')
                ts = float(ts) / 1000.
                tid = int(tid)
                if self.min_time is None:
                    self.min_time = ts
                if aid not in self.data:
                    self.data[aid] = []
                self.data[aid].append((ts - self.min_time, tid))
                self.n_tubes = max(self.n_tubes, tid)
        # run duration in seconds
        self.duration = ts - self.min_time
        
        if n_tubes is None:
            # n_tubes is 1 more than max
            self.n_tubes += 1
        else:
            self.n_tubes = n_tubes
        
        # pre-compute tube vectors
        radius = 200
        radius_temp = radius
        animal_radius_offset = 10
        self.animal_radii = {}
        for aid in self.data:
            self.animal_radii[aid] = radius_temp
            radius_temp -= animal_radius_offset

        self.tube_vectors = []
        for i in range(self.n_tubes):
            p = i / self.n_tubes * 2. * numpy.pi
            x = numpy.cos(p)
            y = numpy.sin(p)
            self.tube_vectors.append(numpy.array([x, y]))
        
        # compute a reasonable time compression
        self.fade_per_frame = 0.3
        self.fps = 30
        animation_duration = 120
        n_frames = self.fps * animation_duration
        self.seconds_per_frame = self.duration / n_frames
        #self.seconds_per_frame = 10.
        
        self.frame_time = 0
        
        self.read_lists = {k: ReadList(self.data[k]) for k in self.data}

        self.scatters = {}
        self.lines = {}
        self.animal_colors = {}
        cm = matplotlib.cm.hsv
        for (i, aid) in enumerate(self.data):
            c = cm(i / (len(self.data) - 1))
            self.animal_colors[aid] = c
            # draw points for last position
            self.scatters[aid] = pylab.scatter([], [], color=c)
            # draw lines for previous positions
            #self.lines[aid] = pylab.plot([], [], color=c)[0]
            self.lines[aid] = []

        self.fig = pylab.gcf()
        self.ax = pylab.gca()
        self.ax.set_xlim(
            -radius-animal_radius_offset, radius + animal_radius_offset)
        self.ax.set_ylim(*self.ax.get_xlim())
        #self.ax.set_ylim(-radius-radius_, radius)
        self.ax.set_aspect(1.0)
        
        self.ani = matplotlib.animation.FuncAnimation(
            self.fig, self.update_display, interval=1000 / self.fps,
            blit=True, repeat=False, frames=n_frames)

    def show(self):
        pylab.show()
    
    def save(self, fn, writer_name):
        writer = matplotlib.animation.writers[writer_name](self.fps)
        self.ani.save(fn, writer=writer)

    def update_display(self, i):
        if i % 30 == 0:
            print("Rendering", i)
        # advance frame time
        self.frame_time += self.seconds_per_frame

        # check if animal animals have moved
        moves = {}
        for aid in self.data:
            r = self.read_lists[aid]
            while (r.get() is not None and r.get()[0] <= self.frame_time):
                moves[aid] = moves.get(aid, []) + [r.get()[1], ]
                r.advance()

        # update display for all moves
        for aid in moves:
            tids = moves[aid]
            xys = [
                self.tube_vectors[tid] * self.animal_radii[aid]
                for tid in tids]
            # get previous position
            pxy = self.scatters[aid].get_offsets()
            if len(pxy):
                pxy = pxy[0]
                xys = numpy.array([pxy,] + xys)
            if len(xys) > 1:
                # TODO fade all previous lines
                remove = []
                for l in self.lines[aid][:]:
                    a = l.get_alpha()
                    if a < self.fade_per_frame:
                        remove.append(l)
                    else:
                        l.set_alpha(a - self.fade_per_frame)
                [self.lines[aid].remove(r) for r in remove]
                xys = numpy.array(xys)
                # add new line
                l = self.ax.plot(
                    xys[:, 0], xys[:, 1], c=self.animal_colors[aid],
                    alpha=1.0)[0]
                self.lines[aid].append(l)
            self.scatters[aid].set_offsets(xys[-1:])

        return (
            list(self.scatters.values()) +
            [l for v in self.lines.values() for l in v])


if __name__ == '__main__':
    d = DataSource(fn, ring=ring, n_tubes=n_tubes)
    #d.show()
    d.save('anim.html', 'html')
