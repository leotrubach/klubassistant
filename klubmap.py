from math import degrees
from struct import Struct
from struct import Struct
from collections import namedtuple
from decimal import Decimal
from logging import warning

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

MAP_SIGNATURE = b'CNST'

POS_MIDDLE = 0
POS_START = 1
POS_END = 2

POSITION_CODES = {
    POS_MIDDLE: 'middle',
    POS_START: 'start',
    POS_END: 'end'}

OBJECT_TYPES = {
    1: 'semaphore',
    2: 'station boundary',
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

class NotFoundError(Exception):
    pass

class BlockObject(object):
    def __init__(self, raw_bytes):
        self.fill(ObjectStruct.unpack(raw_bytes))
        self.block = None

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
            self.next_index = bt.nextobj // ObjectStruct.size
        else:
            self.next_index = -1

HM = Decimal(1)/Decimal(10**6)

class Block(object):
    def __init__(self, raw_bytes):
        self.fill(BlockStruct.unpack(raw_bytes))
        self.objects = []

    def fill(self, data):
        self.lincoord = data[0]
        self.lt = Decimal(degrees(data[1] / 10**8)).quantize(HM)
        self.ln = Decimal(degrees(data[2] / 10**8)).quantize(HM)
        self.bools = data[3:33]
        self.firstobj_index = data[33] // ObjectStruct.size
        code = data[34]
        self.position = POSITION_CODES[code & 3] # Last 2 bits
        self.radio_freq = (code >> 2) & 15 # Bits 2-5
        self.roadcross = ((code >> 6) & 1) == 1 # Bit 6
        self.increase_even = ((code >> 7) & 1) == 1 # Bit 7

    def __str__(self):
        return (
            'coord={s.lincoord}, lon={s.ln}, lat={s.lt}, '
            'pos={s.position} freq={s.radio_freq}, cross={s.roadcross}, '
            'inc_even={s.increase_even}').format(s=self)

class MapFile(object):
    """A low-level map file access"""
    def __init__(self, name):
        self.objects = []
        self.chains = []
        self._fobj = open(name, mode='rb')
        self.process_header(self._fobj.read(HeaderStruct.size))
        self.chains = list(self.block_chains())
        self.read_objects()
        self.check_chains()
        self.map_chain_objects()
        self.clean_chains()
        self.map_chain_posdicts()

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
            b = Block(self._fobj.read(BlockStruct.size))
            yield b

    def block_chains(self):
        chain = []
        for b in self.read_blocks():
            if b.position == 'start':
                chain = []
                chain.append(b)
            elif b.position == 'middle':
                chain.append(b)
            elif b.position == 'end':
                chain.append(b)
                yield chain[:]
                chain = []
        if chain:
            yield chain # Last chain (if it's without end block)

    def check_chains(self):
        # Check that chains start and end properly
        for c in self.chains:
            if c[0].position != 'start':
                warning('Chain found without start')
            if c[-1].position != 'end':
                warning('Chain found without end')

    def clean_chains(self):
        for i in range(len(self.chains)):
            clean_chain = []
            dirty_chain = self.chains[i]
            for b in dirty_chain:
                if not (45 < b.ln < 90) and not (39 < b.lt < 57):
                    if b.firstobj_index != -1:
                        warning('Found object with 0 coordinates but nonempty')
                else:
                    clean_chain.append(b)
            self.chains[i] = clean_chain
        new_chains = []
        new_chain_objects = []
        for i in range(len(self.chains)):
            if self.chains[i]:
                new_chains.append(self.chains[i])
                new_chain_objects.append(self.chain_objects[i])
        self.chains = new_chains
        self.chain_objects = new_chain_objects

    def map_chain_objects(self):
        self.chain_objects = [list() for i in range(len(self.chains))]
        for i in range(len(self.chains)):
            c = self.chains[i]
            co = self.chain_objects[i]
            for b in c:
                no = b.firstobj_index
                while no != -1:
                    o = self.objects[no]
                    co.append(o)
                    no = o.next_index

    def map_chain_posdicts(self):
        self.chain_posdicts = [dict() for i in range(len(self.chains))]
        for i in range(len(self.chains)):
            c = self.chains[i]
            pd = self.chain_posdicts[i]
            for b in c:
                pd[b.lincoord // 1000] = (b.ln, b.lt)

    def find_coordinates(self, ic, lincoord):
        pd = self.chain_posdicts[ic]
        a = lincoord // 1000
        left = a
        right = a + 1
        tries = 0
        while not left in pd:
            if tries > 5:
                raise NotFoundError
            left -= 1
            tries += 1
        while not right in pd:
            if tries > 5:
                raise NotFoundError
            right += 1
            tries += 1
        lnb, ltb = pd[left]
        lne, lte = pd[right]
        dln = lne - lnb
        dlt = lte - ltb
        from_left = Decimal((a-left) * 1000 + lincoord % 1000)
        left_right = (right - left)*1000
        d =  from_left / left_right
        return lnb + dln * d, ltb + dlt * d

    def read_objects(self):
        self._fobj.seek(self._objoffset)
        while True:
            l = self._fobj.read(ObjectStruct.size)
            if len(l) < ObjectStruct.size:
                break
            self.objects.append(BlockObject(l))