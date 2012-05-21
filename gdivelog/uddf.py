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


def _mix_ref(divetank):
    if divetank.dive_tank_He <= 0.0:
        if divetank.dive_tank_O2 == 21.0 or divetank.dive_tank_O2 <= 0.0:
            return 'mix_air'
        else:
            return 'mix_ean%.1f' % divetank.dive_tank_O2
    return 'mix_tx_%.1f_%.1f' % (divetank.dive_tank_O2, divetank.dive_tank_He)


def _tank_ref(tank_id):
    return 'tank_%d' % tank_id


def _volume_for_tank(preferences, tank):
    # Attempt to haphazard the damn tank volume...
    volume = None
    if preferences.volume_unit == 'c':
        if tank.tank_volume > 0 and tank.tank_wp > 0:
            air_volume = tank.tank_volume * 28.3168466
            if preferences.pressure_unit == 'p':
                cylinder_pressure = tank.tank_wp * 0.0689475729
            else:
                cylinder_pressure = tank.tank_wp
            volume = air_volume / cylinder_pressure
    else:
        if tank.tank_volume > 0:
            volume = tank.tank_volume / 1000
    return volume


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


    def add_divers_and_equipment(self):
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
        for tank in self.db.tanks():
            piece_group = self._add(equipment_group, 'tank', subfields={'name': tank.tank_name}, attr={'id': _tank_ref(tank.tank_id)})
            self._add(piece_group, 'volume', _volume_for_tank(self.preferences, tank))
            self._add_text_paragraphs(piece_group, 'notes', tank.tank_notes)

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
        # Also create a dict {diveid: [(dive_tank_stime, dive_tank_id)]}.
        # This way, while creating waypoints, lookup the list and when then
        # divetime field crosses the dive_tank_stime, lookup the dive_tank_id,
        # add a <tankdata> field to the dive, and a <switchmix> field to the <waypoint>
        cache = set()
        for dive_tank in self.db.dive_tanks():
            ref = _mix_ref(dive_tank)
            if ref not in cache:
                mix_group = self._add(gasdefinitions, 'mix', attr={'id': ref})
                if dive_tank.dive_tank_O2 > 0:
                    f_o2 = dive_tank.dive_tank_O2/100.0
                    self._add(mix_group, 'o2', f_o2)
                if dive_tank.dive_tank_He > 0.0:
                    f_he = dive_tank.dive_tank_He/100.0
                    self._add(mix_group, 'he', f_he)
                cache.add(ref)
            # FIXME: enforce there's always a mix_air in it...


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
            # FIXME: check temperature units
            self._add(dive_group, 'lowesttemperature', celcius_to_kelvin(dive.dive_mintemp))
        self._add(dive_group, 'greatestdepth', dive.dive_maxdepth)
        self._add(dive_group, 'altitude', text=0)
        self._add(dive_group, 'density', text=1030)
        self._add(dive_group, 'duration', dive.dive_duration)
        self._add(dive_group, 'apparatus', 'open-scuba') # gdivelog doesn't do anything else...
        self._add_text_paragraphs(dive_group, 'notes', dive.dive_notes)

        # Stimes is a list of (starttime, mixref), so while traversing dive times for the waypoint samples, we can pop off elements as switches are made.
        stimes = []
        for dive_tank in self.db.dive_tanks(diveid=dive.dive_id):
            if dive_tank.dive_tank_stime > 0 and dive_tank.dive_tank_etime > 0:
                stimes.append((dive_tank.dive_tank_stime, _mix_ref(dive_tank)))
            tank_group = self._add(dive_group, 'tankdata')
            self._add(tank_group, 'link', attr={'ref': _tank_ref(dive_tank.tank_id)})
            self._add(tank_group, 'link', attr={'ref': _mix_ref(dive_tank)})
            tank = self.db.tank_by_id(dive_tank.tank_id)
            self._add(tank_group, 'volume', _volume_for_tank(self.preferences, tank))
            # FIXME: convert to pascal
            self._add(tank_group, 'tankpressurebegin', dive_tank.dive_tank_spressure)
            self._add(tank_group, 'tankpressureend', dive_tank.dive_tank_epressure)

        if stimes:
            stimes[0] = (0, stimes[0][1])
        else:
            stimes = [(0, 'mix_air')]

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
            waypoint = self._add(sample_group, 'waypoint', subfields={'divetime': sample.profile_time, 'depth': sample.profile_depth})
            if stimes and sample.profile_time >= stimes[0][0]:
                self._add(waypoint, 'switchmix', attr={'ref': stimes[0][1]})
                stimes.pop(0)
            # FIXME: check temperature units
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



