from datetime import datetime
import xml.dom.minidom

from gdivelog.utils import celcius_to_kelvin, celcius_to_fahrenheit, xml_add
from gdivelog import SI_INF, NAME, VERSION

__all__ = ['GDiveLogUDCF']
__author__ = "Eskil Heyn <eskil@eskil.org>"
__maintainer__ = "Eskil Olsen <eskil@eskil.org>"
__copyright__ = "Copyright 2011"
__license__ = "Public Domain"
__version__ = "1.0"
__status__ = "Production"


class GDiveLogUDCF(object):
    """
    Represent a GDivelog database as a UDCF document.

    Note: UDCF is discontinued, so don't bother putting too much effort into this thing.
    """

    def __init__(self, options, preferences):
        self.options = options
        self.preferences = preferences
        self.top = xml.dom.minidom.Document()
        # Put in the <generator> header.
        self.doc = self._add(self.top, 'profile', attr={'udcf': 1})
        if self.preferences.depth_unit == 'm':
            self._add(self.doc, 'units', text='Metric')
        else:
            self._add(self.doc, 'units', text='Imperial')
        self._add(self.doc, 'device', subfields={'vendor': NAME, 'model': 'udcf', 'version': VERSION})


    def _add(self, node, tag, text=None, subfields={}, attr={}):
        '''Helper function to add tag to node via xml_add'''
        return xml_add(self.top, node, tag, text=text, subfields=subfields, attr=attr)


    def add_dives(self, divelog, args):
        """
        Add all known dives to the UDCF document.
        """
        previous_divetime = datetime.min
        group = self._add(self.doc, 'repgroup')

        for dive in divelog.dives(numbers=args):
            # Compute the SI and start a new group if INF
            divetime = datetime.strptime(dive.dive_datetime, '%Y-%m-%d %H:%M:%S')
            surfaceinterval = divetime - previous_divetime
            dive_group = self._add(group, 'dive')

            self._add(dive_group, 'date', subfields={'year': divetime.year, 'month': divetime.month, 'day': divetime.day})
            self._add(dive_group, 'time', subfields={'hour': divetime.hour, 'minute': divetime.minute})

            if surfaceinterval > SI_INF:
                self._add(dive_group, 'surface_interval', subfields={'infinity': None})
            else:
                self._add(dive_group, 'surface_interval', subfields={'passedtime': surfaceinterval.days * 24 * 60 * 60 + surfaceinterval.seconds}) # .total_seconds in 2.7...

            if celcius_to_kelvin(dive.dive_mintemp) > 0:
                if self.preferences.depth_unit == 'm':
                    self._add(dive_group, 'temperature', dive.dive_mintemp)
                else:
                    self._add(dive_group, 'temperature', celcius_to_fahrenheit(dive.dive_mintemp))
            self._add(dive_group, 'density', text=1030.0)
            self._add(dive_group, 'altitude', text=0.0)

            # FIXME:...
            gases_group = self._add(dive_group, 'gases')
            mix_group = self._add(gases_group, 'mix', subfields={'mixname': 1, 'o2': 0.21, 'n2': 0.79, 'he': 0.0})
            tank_group = self._add(mix_group, 'tank', subfields={'tankvolume': 10, 'pstart': 250, 'pend': 30})

            if dive.site_id > 0:
                self._add(dive_group, 'place', text=divelog.site_name(dive.site_id))

            self._add(dive_group, 'timedepthmode')
            sample_group = self._add(dive_group, 'samples', subfields={'switch': 1})
            self._add(sample_group, 't', text=0)
            self._add(sample_group, 'd', text=0)
            for sample in divelog.samples(dive.dive_id):
                self._add(sample_group, 't', text=sample.profile_time)
                self._add(sample_group, 'd', text=sample.profile_depth)
            self._add(sample_group, 't')
            self._add(sample_group, 'd', text=0)

            previous_divetime = divetime
