from decimal import Decimal
from logging import warning
from klubmap import MapFile, NotFoundError
import simplekml

maps = ('3.map', '2.map')
kml = simplekml.Kml()
kml.document.name = 'Railways Map'

coords = []
groups = []
final_groups = []
current_group = []
stations = []


def draw_chain(name, chain, k):
    ls = k.newlinestring(name=name)
    ls.coords = [(b.ln, b.lt) for b in chain]

for m in [MapFile(m) for m in maps]:
    for i in range(len(m.chains)):
        c = m.chains[i]
        draw_chain('segment %d' % (i,), c, kml)
        objects = m.chain_objects[i]
        for o in objects:
            if o.way in (1, 2) and o.objtype == 'station boundary':
                try:
                    coords = m.find_coordinates(i, o.linaddr)
                    print(o.name.decode('cp1251'), coords)
                    name = o.name.decode('cp1251')
                    p = kml.newpoint(name=name)
                    p.coords = [coords]
                except NotFoundError:
                    warning('Could not find coords for point %s' % name)


kml.save('out.kml')
