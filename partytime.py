#!/usr/bin/env python
"""
Auto-find teensy [done]
No longer save touch logs [done]
Time sync [done]
Update occupancy calc (to not use beam breaks)
by default turn on ui?
auto-determine number of cages/tubes
"""

import argparse
import datetime
import logging
import os
import sys
import time

import serial
import serial.tools.list_ports

if sys.version_info[0] == 2:
    import Tkinter as tk
else:
    import tkinter as tk


logging.basicConfig(level=logging.WARNING)

cages = {}
tubes = {}

EVENT_RFID = 0
EVENT_BEAM = 1
EVENT_TOUCH = 2
EVENT_SYNC = 3
EVENT_ANALOG_PD = 4

event_strings = {
    EVENT_RFID: 'rfid',
    EVENT_BEAM: 'beam',
    EVENT_TOUCH: 'touch',
    EVENT_SYNC: 'sync',
    EVENT_ANALOG_PD: 'analog_pd',
}

event_data_types = {
    EVENT_RFID: lambda d0, d1: (d0, int(d1)),
    EVENT_BEAM: lambda d0, d1: (d0, d1),
    EVENT_TOUCH: lambda d0, d1: (int(d0), int(d1)),
    EVENT_SYNC: lambda d0, d1: (int(d0), int(d1)),
    EVENT_ANALOG_PD: lambda d0, d1: (int(d0), int(d1)),
}


class Event:
    def __init__(
            self, timestamp, board_id, event_id, data0, data1, raw_message):
        self.raw_message = raw_message
        self.timestamp = timestamp
        self.board_id = board_id
        self.event_id = event_id
        self.event_string = event_strings.get(event_id, 'unknown')
        if self.event_id in event_data_types:
            self.data0, self.data1 = event_data_types[event_id](data0, data1)
        else:
            self.data0, self.data1 = (data0, data1)


def parse_event_message(msg):
    if isinstance(msg, (bytes, bytearray)):
        msg = msg.decode('utf-8')
    msg = msg.strip()
    if (len(msg) == 0) or (msg[0] == '#'):
        # comment/debug message
        logging.debug(msg)
        return None
    ts = msg.split(",")
    if len(ts) != 5:
        # log invalid message
        logging.error("Invalid message: %s", msg)
        return None
    t, bid, eid, d0, d1 = ts
    return Event(int(t), int(bid, 16), int(eid), d0, d1, msg)


class BlockParty:
    def __init__(
            self, port, log_directory, log_rollover_time=240,
            allow_multiple_reconnects=True):
        self.tubes = {}
        self.mice = {}
        self.port = port
        self.allow_multiple_reconnects = allow_multiple_reconnects
        self._connect_to_port()
        
        self.log_directory = log_directory
        # rollover time in minutes
        self.log_rollover_time = log_rollover_time
        if self.log_directory is not None:
            if not os.path.exists(self.log_directory):
                os.makedirs(self.log_directory)
            if not os.path.isdir(self.log_directory):
                raise IOError("%s is not a directory" % (self.log_directory, ))
            self._roll_logs()
    
    def _connect_to_port(self):
        try:
            self.connection = serial.Serial(self.port, 9600)
        except serial.SerialException as e:
            self.connection = None
            return False, e
        if not hasattr(self.connection, 'in_waiting'):
            # patch serial.Serial for backwards compatibility
            self.connection.in_waiting = self.connection.inWaiting
        return True, None
    
    def __del__(self):
        self._close_logs()
    
    def _close_logs(self):
        #if hasattr(self, 'touch_log_file'):
        #    logging.debug("Closing touch log file")
        #    self.touch_log_file.close()
        if hasattr(self, 'event_log_file'):
            logging.debug("Closing event log file")
            self.event_log_file.close()

    def _roll_logs(self):
        if self.log_directory is None:
            return
        self._close_logs()
        self.log_start_time = datetime.datetime.now()
        ts = self.log_start_time.strftime('%y%m%d_%H%M%S')
        bfn = os.path.join(self.log_directory, ts)
        #self.touch_log_filename = bfn + '_touch.csv'
        self.event_log_filename = bfn + '.csv'
        #self.touch_log_file = open(self.touch_log_filename, 'w')
        self.event_log_file = open(self.event_log_filename, 'w')
        self.connection.write('t'.encode())

    def reset_counts(self):
        for bid in self.tubes:
            t = self.tubes[bid]
            if 'nreads' in t['rfid']:
                t['rfid']['nreads'] = 0
            if 'reads' in t['rfid']:
                t['rfid']['reads'] = []
            if 'reads_per_second' in t['rfid']:
                t['rfid']['reads_per_second'] = 0
            if 'nbreaks' in t['beam']['left']:
                t['beam']['left']['nbreaks'] = 0
            if 'nbreaks' in t['beam']['right']:
                t['beam']['right']['nbreaks'] = 0
        for tag in self.mice:
            m = self.mice[tag]
            if 'nreads' in m:
                m['nreads'] = 0

    def update_reads_per_second(self):
        t = time.time()
        for bid in self.tubes:
            r = self.tubes[bid]['rfid']
            if 'reads' not in r:
                continue
            reads = r['reads']
            reads = [r for r in reads if t - r <= 1.0]
            r['reads'] = reads
            r['reads_per_second'] = len(reads)

    def update_colony(self, event):
        """Handle an incoming event
        
        return True if the party has changed"""
        changed = False
        if event.board_id not in self.tubes:
            self.tubes[event.board_id] = {
                'rfid': {},
                'beam': {
                    'left': {},
                    'right': {},
                },
            }
            changed = True
        if event.event_id == EVENT_RFID:
            reads = self.tubes[event.board_id]['rfid'].get('reads', [])
            # filter out old reads
            t = time.time()
            reads = [r for r in reads if t - r <= 1.0]
            reads.append(t)
            self.tubes[event.board_id]['rfid'] = {
                'id': event.data0,
                'timestamp': event.timestamp,
                'nreads': self.tubes[event.board_id]['rfid'].get('nreads', 0) + 1,
                'reads': reads,
                'reads_per_second': len(reads),
            }
            self.mice[event.data0] = {
                'tube': event.board_id,
                'datetime': datetime.datetime.now(),
                'nreads': self.mice.get(event.data0, {}).get('nreads', 0) + 1,
            }
            changed = True
        elif event.event_id == EVENT_BEAM:
            if (event.data1 == 'b'):
                if (event.data0 == 'L'):
                    side = 'left'
                else:
                    side = 'right'

                self.tubes[event.board_id]['beam'][side] = {
                    'nbreaks': self.tubes[event.board_id]['beam'][side].get('nbreaks', 0) + 1,
                }
        return changed

    def log_event(self, event):
        if self.log_directory is None:
            return
        # if log rollover time exceeded, make new logs
        dt = datetime.datetime.now() - self.log_start_time
        if (dt.seconds > (self.log_rollover_time * 60)):
            logging.debug("Rolling logs")
            self._roll_logs()
        #if event.event_id == EVENT_TOUCH:
        #    f = self.touch_log_file
        #else:
        #    f = self.event_log_file
        f = self.event_log_file
        f.write("%s\n" % event.raw_message)
    
    def process_event(self, event):
        self.log_event(event)
        return self.update_colony(event)

    def update(self, retry=True):
        if self.connection is None:
            succeeded, error = self._connect_to_port()
            if succeeded:
                print("Reconnection succeeded!")
                return self.update(retry=False)
            print("Reconnection attempt failed: %s" % error)
            # try again next time
            if self.allow_multiple_reconnects:
                return False, None
            else:
                raise error
        try:
            if not self.connection.in_waiting:
                return False, None
            l = self.connection.readline()
        except serial.SerialException as e:
            print("Serial exception %s" % e)
            if retry:
                print("attempting to reconnect")
                self.connection = None
                return self.update(retry=retry)
            else:
                raise e
        e = parse_event_message(l)
        changed = False
        if e is not None:
            changed = self.process_event(e)
        return changed, e


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-H', '--headless', default=False, action='store_true',
        help="Don't show the ui")
    parser.add_argument(
        '-l', '--log_directory', default='logs',
        help="Log directory")
    parser.add_argument(
        '-L', '--no_log_directory_timestamp',
        default=False, action='store_true',
        help="Don't add a timestamp to the log directory")
    #parser.add_argument(
    #    '-n', '--n_tubes', type=int, default=-1,
    #    help="Number of tubes in colony (only needed for ui)")
    parser.add_argument(
        '-p', '--port', default=None,
        help="Serial port to which the colony is connected")
    parser.add_argument(
        '-r', '--rollover_time', default=240, type=int,
        help="Maximum duration of each log file")
    parser.add_argument(
        '-s', '--silent', default=False, action='store_true',
        help="Disable logging")
    #parser.add_argument(
    #    '-t', '--track_colony', default=False, action='store_true',
    #    help="Also track the colony, reporting mouse movements")
    #parser.add_argument(
    #    '-T', '--rfid_timeout', default=1000, type=int,
    #    help="maximum time to wait after rfid read for a beam break")
    parser.add_argument(
        '-u', '--ui', default=False, action='store_true',
        help="Display a ui (forces track_colony to True and requires n tubes)")
    parser.add_argument(
        '-v', '--verbose', default=False, action='store_true',
        help="Enable verbose debugging")
    args = parser.parse_args()
    if args.port is None:
        ps = serial.tools.list_ports.comports()
        ts = []
        for p in ps:
            if p.pid == 1155 and p.vid == 5824:  # check if teensy
                ts.append(p.device)
        if len(ts) > 1:
            raise ValueError("Found >1 teensy: %s" % (ts, ))
        if len(ts) == 0:
            raise ValueError("Found no teensies")
        print("Found teensy at port: %s" % ts[0])
        args.port = ts[0]
    if not args.no_log_directory_timestamp:
        d = os.path.abspath(args.log_directory)
        # prepend with datetime string
        d += '_%s' % (datetime.datetime.now().strftime('%y%m%d_%H%M%S'), )
        args.log_directory = d
    print("Log directory: %s" % (args.log_directory, ))
    if args.silent:
        args.log_directory = None
    if args.verbose:
        logging.root.setLevel(logging.DEBUG)
    return args


def command_line_run(args):
    bp = BlockParty(
        args.port, args.log_directory,
        log_rollover_time=args.rollover_time)
    while True:
        try:
            bp.update()
            time.sleep(0.001)
        except KeyboardInterrupt:
            break

            
class MainWindow:
    def __init__(self, block_party):
        self.party = block_party
        self.root = tk.Tk()
        self.tube_rows = []
        self.mouse_rows = []
        # title = log directory
        # per cage: [ID] [N] : rfids...
        tk.Button(
            self.root, text="Reset counts", command=self.reset_counts).pack()
        base_frame = tk.Frame(self.root)
        base_frame.pack()
        #base_frame = self.root
        # make labels
        #f = tk.Frame(base_frame)
        #f.pack(side=tk.TOP, fill=tk.X)
        #tk.Label(f, text="Tube").pack(side=tk.LEFT)
        #tk.Label(f, text="N").pack(side=tk.LEFT)
        #tk.Label(f, text="IDS").pack(side=tk.LEFT)
        self.tube_frame = tk.Frame(base_frame)
        self.tube_frame.grid(row=0, column=0)
        f = self.tube_frame
        for (i, t) in enumerate(('Tube', 'LBB', 'RFID', 'RBB', 'NReads', 'RPS')):
            tk.Label(f, text=t).grid(row=0, column=i)
        self.mouse_frame = tk.Frame(base_frame, bd=2, relief='groove')
        self.mouse_frame.grid(row=0, column=1)
        f = self.mouse_frame
        for (i, t) in enumerate(('Mouse', 'Tube', 'NReads', 'Timestamp')):
            tk.Label(f, text=t).grid(row=0, column=i)
        """
        for i in range(n_cages):
            # add cage
            f = tk.Frame(base_frame)
            f.pack(side=tk.TOP, fill=tk.X)
            tk.Label(f, text="   %02i  " % i).pack(side=tk.LEFT)
            nl = tk.Label(f, text="0")
            nl.pack(side=tk.LEFT)
            idf = tk.Frame(f)
            idf.pack(side=tk.LEFT)
            idv = tk.StringVar(value="")
            ide = tk.Entry(idf, textvariable=idv, state='readonly')
            ide.pack(side=tk.LEFT)
            idb = tk.Scrollbar(idf, orient='horizontal', command=ide.xview)
            idb.pack(side=tk.TOP)
            #ids = tk.Label(f, text="")
            #ids.pack(side=tk.LEFT)
            #self.cages[i] = {
            #    'n': nl,
            #    #'ids': ids,
            #    'ids': idv,
            #}
            #if i == (n_cages - 1):  # don't add tube
            #    continue
            # add tube
            f = tk.Frame(base_frame)
            f.pack(side=tk.TOP)
            lb = tk.Label(f, text="?")
            lb.pack(side=tk.LEFT)
            rfid = tk.Label(f, text="??????????")
            rfid.pack(side=tk.LEFT)
            rb = tk.Label(f, text="?")
            rb.pack(side=tk.LEFT)
            self.tubes[i] = {
                'lb': lb,
                'rfid': rfid,
                'rb': rb,
            }
        """
    
    def add_tube_row(self):
        # 'Tube', 'LBB', 'RFID', 'RBB'
        row = {}
        f = self.tube_frame
        ri = len(self.tube_rows) + 1
        for (i, t) in enumerate(('Tube', 'LBB', 'RFID', 'RBB', 'NReads', 'RPS')):
            if t == 'Tube':
                row[t] = tk.Label(f, text='%i' % len(self.tube_rows))
            else:
                row[t] = tk.Label(f, text='?')
            row[t].grid(row=ri, column=i)
        self.tube_rows.append(row)
    
    def add_mouse_row(self):
        # 'Mouse', 'Tube', 'Timestamp'
        row = {}
        f = self.mouse_frame
        ri = len(self.mouse_rows) + 1
        for (i, t) in enumerate(('Mouse', 'Tube', 'NReads', 'Timestamp')):
            row[t] = tk.Label(f, text='?')
            row[t].grid(row=ri, column=i)
        self.mouse_rows.append(row)
    
    def redraw_mouse_rows(self):
        rfids = sorted(list(self.party.mice.keys()))
        for (ri, rfid) in enumerate(rfids):
            r = self.mouse_rows[ri]
            md = self.party.mice[rfid]
            r['Mouse'].config(text=rfid)
            r['Tube'].config(text=md['tube'])
            r['NReads'].config(text=md['nreads'])
            r['Timestamp'].config(text=md['datetime'].ctime())
    
    def update_reads_per_second(self):
        self.party.update_reads_per_second()
        for bid in self.party.tubes:
            d = self.party.tubes[bid]['rfid']
            if 'reads' not in d:
                continue
            r = self.tube_rows[bid]
            r['RPS'].config(
                text=str(d['reads_per_second']))
        self.root.after(1000, self.update_reads_per_second)

    def reset_counts(self):
        self.party.reset_counts()
        for bid in self.party.tubes:
            r = self.tube_rows[bid]
            r['NReads'].config(text="0")
            r['RPS'].config(text="0")
        self.redraw_mouse_rows()

    def update(self):
        changed, event = self.party.update()
        if changed:
            while max(list(self.party.tubes.keys())) + 1 > len(self.tube_rows):
                self.add_tube_row()
            while len(self.party.mice) > len(self.mouse_rows):
                self.add_mouse_row()
            self.redraw_mouse_rows()
        if event is not None and event.event_id == EVENT_BEAM:
            # redraw beam
            r = self.tube_rows[event.board_id]
            state = event.data1
            if event.data0 == 'L':
                r['LBB'].config(text=state)
            else:
                r['RBB'].config(text=state)
        elif event is not None and event.event_id == EVENT_RFID:
            # show rfid
            r = self.tube_rows[event.board_id]
            r['RFID'].config(text=event.data0)
            r['NReads'].config(
                text=str(
                    self.party.tubes[event.board_id]['rfid']['nreads']))
            r['RPS'].config(
                text=str(
                    self.party.tubes[event.board_id]['rfid']['reads_per_second']))
            # TODO if error, change color?
        # re-register update
        self.root.after(1, self.update)
    
    def run(self):
        # register update callback
        self.update()
        self.update_reads_per_second()
        self.root.mainloop()

def ui_run(args):
    bp = BlockParty(
        args.port, args.log_directory,
        log_rollover_time=args.rollover_time)
    mw = MainWindow(bp)
    mw.run()


if __name__ == '__main__':
    args = parse_arguments()
    if args.headless:
        print("Running script [Ctrl-C] to quit")
        command_line_run(args)
    else:
        ui_run(args)