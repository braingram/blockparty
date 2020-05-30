
import numpy
import pylab

import matplotlib
import matplotlib.animation


fn = 'reads.csv'
ring = True
n_tubes = None  # None: guess from data
seconds_per_frame = 10  # None: compute assuming 2 minute animation
# if animals is None, default colormap will be used
# if animals is a list, only these animals will be plotted
#  and the default color map will be used
# if animals is a dict, only these animals will be plotted
#  and animals will be colored by the value where value can be
#   - color (see matplotlib colors)
#   - colormap (see matplotlib colormaps)
animals = None

# animals = ["002FBE7309", "002FBE7189"]

# animals = {
#     "002FBE7309": matplotlib.cm.jet,
#     "002FBE7189": matplotlib.cm.hsv,
# }

# animals = {
#     "2A006D4CAA": "#FF3399",
#     "2A006D5A23": "#FF80BF",
#     "2A006D2C01": "#FF0080",
#     "2A006D4225": "#FF198C",
#     "2A006D521F": "#FF66B3",
#     "2A006D5CED": "#FFB3D9",
#     "2A006D5AF7": "#FF99CC",
#     "2A006D4F9F": "#FF4DA6",
#     "2A006D2DB9": "#4DFFA6",
#     "2A006D2D1B": "#33FF99",
#     "2A006D2AF5": "#19FF8C",
#     "2A006D69CD": "#B3FFD9",
#     "2A006D2AD5": "#00FF80",
#     "2A006D30B6": "#66FFB3",
#     "2A006D5211": "#99FFCC",
#     "2A006D4D51": "#80FFBF",
# }

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
    def __init__(
            self, fn, ring=True, n_tubes=None, animals=None,
            seconds_per_frame=None):
        self.n_tubes = 0
        self.min_time = None
        if animals is None:
            valid_animal = lambda aid: True
        else:
            valid_animal = lambda aid: aid in animals
        self.data = {}  # by animal id: (timestamp offset, tube id)
        # read in data
        with open(fn, 'r') as f:
            for l in f:
                if not len(l.strip()):
                    continue
                ts, aid, tid = l.strip().split(',')
                ts = float(ts) / 1000.
                tid = int(tid)
                self.n_tubes = max(self.n_tubes, tid)
                if self.min_time is None:
                    self.min_time = ts
                if not valid_animal(aid):
                    continue
                if aid not in self.data:
                    self.data[aid] = []
                self.data[aid].append((ts - self.min_time, tid))
        print("N animals: %s" % len(self.data))
        if len(self.data) == 0:
            raise Exception("No valid animals found")
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
        if seconds_per_frame is None:
            animation_duration = 120
            n_frames = self.fps * animation_duration
            self.seconds_per_frame = self.duration / n_frames
        else:
            self.seconds_per_frame = seconds_per_frame
            n_frames = int(numpy.ceil(self.duration / self.seconds_per_frame))


        self.frame_time = 0

        self.read_lists = {k: ReadList(self.data[k]) for k in self.data}

        default_cm = matplotlib.cm.hsv
        # make color maps for animals
        if animals is None or not isinstance(animals, dict):
            self.animal_colors = {
                aid: default_cm(i / (max(1.0, len(self.data) - 1.0)))
                for (i, aid) in enumerate(self.data)}
        else:  # animals is a dict
            # key can be a color map or a color
            # find animals with matching colormap
            animals_by_colormap = {}
            self.animal_colors = {}
            for aid in self.data:
                if aid not in animals:
                    cm = default_cm
                elif isinstance(animals[aid], matplotlib.colors.Colormap):
                    cm = animals[aid]
                else:
                    if not matplotlib.colors.is_color_like(animals[aid]):
                        raise ValueError("Invalid color:%s" % (animals[aid], ))
                    self.animal_colors[aid] = animals[aid]
                    continue  # assume animals[aid] is a color
                if cm not in animals_by_colormap:
                    animals_by_colormap[cm] = []
                animals_by_colormap[cm].append(aid)
            # for each color map found, assign colors to animals
            for cm in animals_by_colormap:
                cm_animals = animals_by_colormap[cm]
                for (i, aid) in enumerate(cm_animals):
                    self.animal_colors[aid] = cm(i / max(1.0, len(cm_animals) - 1.0))
        print(self.animal_colors)
        self.scatters = {}
        self.lines = {}
        for aid in self.data:
            # generate animal color from color map
            c = self.animal_colors[aid]
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
    d = DataSource(
        fn, ring=ring, n_tubes=n_tubes, animals=animals,
        seconds_per_frame=seconds_per_frame)
    d.show()
    #d.save('anim.html', 'html')
