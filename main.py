import sys
from PySide import QtCore, QtGui
from PySide.QtWebKit import QWebView
import math
from decimal import Decimal

ST_MAPS_API = 'http://maps.googleapis.com/maps/api/staticmap?'

PI = Decimal(math.pi)
SIX_PLACES = Decimal('0.000001')

def coord_conv(club_coords):
    return Decimal(club_coords * 180 / (PI * 100000000)).quantize(SIX_PLACES)

class AssistantWindow(QtGui.QDialog):
    def __init__(self, *args, **kwargs):
        super(AssistantWindow, self).__init__(*args, **kwargs)
        self.smap = QWebView()
        self.lattitude = QtGui.QLineEdit()
        self.longitude = QtGui.QLineEdit()
        self.get_map_button = QtGui.QPushButton('Get map')
        self.get_map_button.clicked.connect(self.get_map)
        self.zoom_level = QtGui.QLineEdit()
        self.zoom_level.setText('18')
        self.flayout = QtGui.QFormLayout()
        self.setLayout(self.flayout)
        self.flayout.addRow('Lattitude:', self.lattitude)
        self.flayout.addRow('Longitude:', self.longitude)
        self.flayout.addRow('Zoom level:', self.zoom_level)
        self.flayout.addRow(self.get_map_button)
        self.flayout.addRow(self.smap)
    
    def get_map(self):
        lt = int(self.lattitude.text())
        ln = int(self.longitude.text())
        lt_g = coord_conv(lt)
        ln_g = coord_conv(ln)
        url = (ST_MAPS_API + 'center=%s,%s' % (lt_g, ln_g) + 
               '&zoom=%s' % self.zoom_level.text() + 
               '&size=400x400&sensor=false&maptype=hybrid' + 
               '&markers=%s,%s' % (lt_g, ln_g))
        self.smap.load(url)

app = QtGui.QApplication(sys.argv)
aw = AssistantWindow()
aw.show()
sys.exit(app.exec_())
