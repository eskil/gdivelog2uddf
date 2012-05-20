from datetime import datetime, timedelta
import xml.dom.minidom
import sys

from gdivelog.utils import celcius_to_kelvin, celcius_to_fahrenheit, xml_add
from gdivelog import SI_INF, NAME, VERSION

__all__ = ['GDiveLogUDDF']
__author__ = "Eskil Heyn <eskil@eskil.org>"
__maintainer__ = "Eskil Olsen <eskil@eskil.org>"
__copyright__ = "Copyright 2011"
__license__ = "Public Domain"
__version__ = "1.0"
__status__ = "Production"


def _dive_ref(dive_id):
    return 'dive_%d' % dive_id

def _site_ref(site_id):
    return 'site_%d' % site_id

def _buddy_ref(buddy_id):
    return 'buddy_%d' % buddy_id

def _equipment_ref(equipment_id):
    return 'eq_%d' % equipment_id

def _trip_ref(trip_id):
    return 'trip_%d' % trip_id

def _repgroup_ref(repgroup_id):
    return 'rg_%d' % repgroup_id

class GDiveLogUDDF(object):
    """
    Represent a GDivelog database as a UDDF document.
    """

    def __init__(self, db, options, preferences, args):
        self.db = db
        self.options = options
        self.preferences = preferences
        self.args = args
        self.top = xml.dom.minidom.Document()
        # Put in the <generator> header.
        self.doc = self._add(self.top, 'uddf', attr={'version': '3.0.0',
                                                     'type': 'converter'})
        generator = self._add(self.doc, 'generator', subfields={'name': NAME, 'version': VERSION, 'type': 'logbook'})
        manufacturer = self._add(generator, 'manufacturer', subfields={'name': 'Eskil Heyn Olsen'})
        contact = self._add(manufacturer, 'contact')
        self._add(contact, 'homepage', 'http://github.com/eskilolsen/gdivelog2uddf')
        self._add(contact, 'homepage', 'http://eskil.org/')
        self._add(generator, 'datetime', datetime.now().isoformat())


    def _add(self, node, tag, text=None, subfields={}, attr={}):
        '''Helper function to add tag to node via xml_add'''
        return xml_add(self.top, node, tag, text=text, subfields=subfields, attr=attr)


    def _add_text_paragraphs(self, node, tag, text):
        """
        Add a text paragraph to 'node' under the tag 'tag'.
        The given text is split at newlines.
        """
        if not text:
            return
        if '<xml>' in text:
            begin = text.find('<xml>')
            end = text.find('</xml>')
            snippet = text[begin:end+len('</xml>')]
            try:
                dom = xml.dom.minidom.parseString(snippet)
                for child in  dom.firstChild.childNodes:
                    if child.nodeType == xml.dom.Node.ELEMENT_NODE:
                        node.appendChild(child)
                text = text.replace(snippet, '')
            except:
                print >> sys.stderr, 'Error in xml in "%s"' % snippet
        group = self._add(node, tag)
        for line in text.split('\n\n'):
            self._add(group, 'para', text=line)


    def add_divers(self):
        """
        Add the divelog owner and all known buddies to the UDDF document.
        """
        divers = self._add(self.doc, 'diver')
        owner = self._add(divers, 'owner', attr={'id': 'owner'})
        self._add(owner, 'personal', subfields={'firstname': 'Your First Name', 'lastname': 'Your Last Name'})
        equipment_group = self._add(owner, 'equipment')
        for equipment in self.db.equipment():
            piece_group = self._add(equipment_group, 'variouspieces', subfields={'name': equipment.equipment_name}, attr={'id': _equipment_ref(equipment.equipment_id)})
            self._add_text_paragraphs(piece_group, 'notes', equipment.equipment_notes)
        for buddy in self.db.buddies():
            buddy_group = self._add(divers, 'buddy', attr={'id': _buddy_ref(buddy.buddy_id)})
            names = buddy.buddy_name.split(' ')
            self._add(buddy_group, 'personal', subfields={'firstname': names[0], 'lastname': ' '.join(names[1:])})
            self._add_text_paragraphs(buddy_group, 'notes', buddy.buddy_notes)


    def add_sites(self):
        """
        Add all known sites to the UDDF document.

        The GDivelog "tree" is lost, since each divesite is formed
        by walking the list of parents and combining using the
        site name seperator.
        """
        divesites = self._add(self.doc, 'divesite')
        for site in self.db.sites():
            site_group = self._add(divesites, 'site', subfields={'name': self.db.site_name(site.site_id)}, attr={'id': _site_ref(site.site_id)})
            self._add_text_paragraphs(site_group, 'notes', site.site_notes)


    def add_divetrips(self):
        """
        Add all divetrip to the UDDF document
        """
        if not self.options.trip_si_threshold:
            return

        divetrips = self._add(self.doc, 'divetrip')
        previous_divetime = datetime.min
        trip_counter = 1

        for dive in self.db.dives(numbers=self.args):
            # Compute the SI and start a new trip if > threshold
            divetime = datetime.strptime(dive.dive_datetime, '%Y-%m-%d %H:%M:%S')
            surfaceinterval = divetime - previous_divetime

            if surfaceinterval > timedelta(days=self.options.trip_si_threshold):
                trip = self._add(divetrips, 'trip', attr={'id': _trip_ref(trip_counter)})
                trip_counter += 1
                self._add(trip, 'name', self.db.site_name(dive.site_id))
                trippart = self._add(trip, 'trippart')
                relateddives = self._add(trippart, 'relateddives')
                # FIXME: http://www.streit.cc/extern/uddf_v300/en/trippart.html others fields to add ?

            self._add(relateddives, 'link', attr={'ref': _dive_ref(dive.dive_id)})
            previous_divetime = divetime

        # Add 1 initial trip.
        # Trip names are the site of the first dive in the trip (keep it simple...)
        # For each dive, if the divetime delta is LT options.tripthreshold, add dive to trip,
        # if not, new trip...



    def add_gasdefinitions(self, gasdefinitions, dive):
        """
        Add all known gas definitions to the UDDF document
        """
        # FIXME: add schema defines for Tank and Dive_Tank.
        # Loop over the specified dives, add <gasdefinitions> tag for
        # for each mix in Dive_Tank used.

        # Keep a dictionary that maps from (o2, he) to the reference
        # tag. This way, we can later reference the gas.

        # Create names ala "Air", "Oxygen", "EANx" and "TxX/Y".

        # Also create a dict {diveid: [(dive_tank_stime, dive_tank_id)]}.
        # This way, while creating waypoints, lookup the list and when then
        # divetime field crosses the dive_tank_stime, lookup the dive_tank_id,
        # add a <tankdata> field to the dive, and a <switchmix> field to the <waypoint>
        pass


    def add_dive(self, repititongroup, surfaceinterval, dive):
        """
        This adds a single <dive> tag to the <repetitiongroup> given.
        """
        divetime = datetime.strptime(dive.dive_datetime, '%Y-%m-%d %H:%M:%S')
        dive_group = self._add(repititongroup, 'dive', attr={'id': _dive_ref(dive.dive_id)})
        self._add(dive_group, 'dive_number', text=dive.dive_number)
        self._add(dive_group, 'tripmembership')
        self._add(dive_group, 'datetime', divetime.isoformat())
        if surfaceinterval > SI_INF:
            self._add(dive_group, 'surfaceintervalbeforedive', subfields={'infinity': None})
        else:
            self._add(dive_group, 'surfaceintervalbeforedive', subfields={'passedtime': surfaceinterval.days * 24 * 60 * 60 + surfaceinterval.seconds}) # .total_seconds in 2.7...

        if dive.dive_mintemp:
            self._add(dive_group, 'lowesttemperature', celcius_to_kelvin(dive.dive_mintemp))
        self._add(dive_group, 'greatestdepth', dive.dive_maxdepth)
        self._add(dive_group, 'altitude', text=0)
        self._add(dive_group, 'density', text=1030)
        self._add(dive_group, 'duration', dive.dive_duration)
        self._add(dive_group, 'apparatus', 'open-scuba') # gdivelog doesn't do anything else...
        self._add_text_paragraphs(dive_group, 'notes', dive.dive_notes)

        # FIXME: need to add <tankdata>, see above...

        if dive.site_id > 0:
            self._add(dive_group, 'link', attr={'ref': _site_ref(dive.site_id)})

        for buddy in self.db.buddies(diveid=dive.dive_id):
            self._add(dive_group, 'link', attr={'ref': _buddy_ref(buddy.buddy_id)})

        equipment_group = self._add(dive_group, 'equipmentused')
        if dive.dive_weight > 0.0:
            self._add(equipment_group, 'leadquantity', dive.dive_weight)
        for equipment in self.db.equipment(diveid=dive.dive_id):
            self._add(equipment_group, 'link', attr={'ref': _equipment_ref(equipment.equipment_id)})
        sample_group = self._add(dive_group, 'samples')
        for sample in self.db.samples(dive.dive_id):
            waypoint = self._add(sample_group, 'waypoint', subfields={'divetime': sample.profile_time,
                                                                      'depth': sample.profile_depth})
            k = celcius_to_kelvin(sample.profile_temperature)
            if k > 0:
                self._add(waypoint, 'temperature', k)


    def add_dives(self):
        """
        Add all known dives to the UDDF document. The is the main
        place to iterate across all dives and accumulate info.
        """
        gasdefinitions = self._add(self.doc, 'gasdefinitions')
        profiledata = self._add(self.doc, 'profiledata')
        previous_divetime = datetime.min
        repititiongroup_counter = 1

        for dive in self.db.dives(numbers=self.args):
            # Compute the SI and start a new group if INF
            divetime = datetime.strptime(dive.dive_datetime, '%Y-%m-%d %H:%M:%S')
            surfaceinterval = divetime - previous_divetime

            if surfaceinterval >= SI_INF:
                repititongroup = self._add(profiledata, 'repetitiongroup', attr={'id': _repgroup_ref(repititiongroup_counter)})
                repititiongroup_counter += 1

            self.add_gasdefinitions(gasdefinitions, dive)
            self.add_dive(repititongroup, surfaceinterval, dive)

            previous_divetime = divetime



