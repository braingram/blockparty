#!/usr/bin/env python

# event types
EVENT_RFID = 0
EVENT_BEAM = 1
EVENT_TOUCH_RAW = 2
EVENT_SYNC = 3
EVENT_ANALOG_PD = 4

event_strings = {
    'rfid': EVENT_RFID,
    'beam': EVENT_BEAM,
    'touch_raw': EVENT_TOUCH_RAW,
    'sync': EVENT_SYNC,
    'analog_pd': EVENT_ANALOG_PD,
}

# columns
TIME_COLUMN = 0
BOARD_COLUMN = 1
EVENT_COLUMN = 2
DATA0_COLUMN = 3
DATA1_COLUMN = 4

# rfid columns
RFID_ID_COLUMN = 3
RFID_ERROR_COLUMN = 4

# beam columns
BEAM_SIDE_COLUMN = 3
BEAM_STATE_COLUMN = 4

# beam side
BEAM_LEFT = 0
BEAM_RIGHT = 1

# beam state
BEAM_UNBROKEN = 0
BEAM_BROKEN = 1

# touch raw columns
TOUCH_LEFT_COLUMN = 3
TOUCH_RIGHT_COLUMN = 4

# touch binary columns
TOUCH_SIDE_COLUMN = 3
TOUCH_STATE_COLUMN = 4

# touch side
TOUCH_LEFT = 0
TOUCH_RIGHT = 1

# touch state
TOUCH_UNTOUCHED = 0
TOUCH_TOUCHED = 1

# rfid state
RFID_VALID = 0


data_strings = {
    EVENT_BEAM: {
        0: {
            'l': BEAM_LEFT,
            'r': BEAM_RIGHT,
        },
        1: {
            'b': BEAM_BROKEN,
            'u': BEAM_UNBROKEN,
        },
    },
    #EVENT_TOUCH_BINARY: {
    #    0: {
    #        'l': TOUCH_LEFT,
    #        'r': TOUCH_RIGHT,
    #    },
    #    1: {
    #        't': TOUCH_TOUCHED,
    #        'u': TOUCH_UNTOUCHED,
    #    },
    #},
}

sides = {
    EVENT_BEAM: [BEAM_LEFT, BEAM_RIGHT],
    #EVENT_TOUCH_BINARY: [TOUCH_LEFT, TOUCH_RIGHT],
}

states = {
    EVENT_BEAM: [BEAM_BROKEN, BEAM_UNBROKEN],
    #EVENT_TOUCH_BINARY: [TOUCH_TOUCHED, TOUCH_UNTOUCHED],
}
