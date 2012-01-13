from struct import Struct
from collections import namedtuple

import kluberrors

HEADER_FORMAT = (
        '=', # Packed record
        '5s', # Map file signature
        '2I', # Direction, shift
        '2b', # Valued bit numbers of lattitude and longitude
        'H', # Count of 500m way parts
        '20s', # Reserved
        'I', # Offset of data blocks
)

BLOCK_FORMAT = (
        '=', # Packed record
        'I', # Linear coordinate
        '2i',# Lattitude, longitude
        '30?', # Enabled
        'i', # Objects pointer
        'b', # Code
)

OBJECT_FORMAT = (
        '=', # Packed record
        'I', # Linear address
        'b', # Object type
        'b', # Way
        '8s', # Name
        'H', # SGreen
        'b', # Allowed speed
        'b', # ALSN frequency
        'H', # Object length
        'H', # Semaphore data
        'i', # Next object offset
)

HeaderStruct = Struct(''.join(HEADER_FORMAT))
BlockStruct = Struct(''.join(BLOCK_FORMAT))
ObjectStruct = Struct(''.join(OBJECT_FORMAT))

HeaderTuple = namedtuple('HeaderTuple', ('signature', 'direction', 'shift', 
'vlattitude', 'vlongitude', 'block_count', 'reserved', 'objoffset'))

ObjectTuple = namedtuple('ObjectTuple', ('linaddr', 'objtype', 'way', 'name', 
    'sgreen', 'syellow', 'alsnfreq', 'objlength', 'semaphoredata', 'nextobj'))

MAP_SIGNATURE = 'CNST'

POS_MIDDLE = 0
POS_START = 1
POS_END = 2

POSITION_CODES = (POS_MIDDLE, POS_START, POS_END)

OBJECT_TYPES = {
    1: 'semaphore',
    2: 'station start',
    3: 'dangerous place',
    4: 'bridge',
    5: 'passby',
    6: 'platform',
    7: 'tunnel',
    8: 'switch',
    9: 'sensor',
    10: 'saut',
    11: 'end',
    12: 'braketest'
}

class BlockObject(object):
    def __init__(self, raw_bytes):
        self.fill(ObjectStruct.unpack(raw_bytes))

    def fill(self, data):
        bt = ObjectTuple._make(data) 
        self.linaddr = bt.linaddr
        self.objtype = OBJECT_TYPES[bt.objtype]
        self.way = bt.way
        self.name = bt.name
        self.sgreen = bt.sgreen
        self.syellow = bt.syellow
        self.alsnfreq = bt.alsnfreq
        self.objlength = bt.objlength
        self.semaphoredata = bt.semaphoredata
        if bt.nextobj != -1:
            self.next_index = bt.nextobj / ObjectStruct.size
        else:
            self.next_index = -1


class Block(object):
    def __init__(self, raw_bytes):
        self.fill(BlockStruct.unpack(raw_bytes))

    def fill(self, data):
        self.lincoord, self.lt, self.ln = data[:3]
        self.bools = data[3:33]
        self.firstobj_index = data[33] / ObjectStruct.size
        code = data[34]
        self.position = code & 3 # Last 2 bits
        self.radio_freq = (code >> 2) & 15 # Bits 2-5
        self.roadcross = ((code >> 6) & 1) == 1 # Bit 6
        self.increase_even = ((code >> 7) & 1) == 1 # Bit 7

class MapFile(object):
    """A low-level map file access"""
    def __init__(self, name):
        self.blocks = []
        self.objects = []
        self._fobj = open(name, mode='rb')
        self.process_header(self._fobj.read(HeaderStruct.size))
        self.read_blocks()
        self.read_objects()

    def process_header(self, raw_bytes):
        ht = HeaderTuple._make(HeaderStruct.unpack(raw_bytes))
        if not ht.signature.startswith(MAP_SIGNATURE):
            raise kluberrors.BadFileSignature
        self.direction = ht.direction
        self.shift = ht.shift
        self.vlattitude = ht.vlattitude
        self.vlongitude = ht.vlongitude
        self.block_count = ht.block_count
        self._objoffset = ht.objoffset

    def read_blocks(self):
        for i in range(self.block_count):
            self.blocks.append(Block(self._fobj.read(BlockStruct.size)))

    def read_objects(self):
        self._fobj.seek(self._objoffset)
        while True:
            l = self._fobj.read(ObjectStruct.size)
            if len(l) < ObjectStruct.size:
                break
            self.objects.append(BlockObject(l))
