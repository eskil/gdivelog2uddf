"""

Convert gdivelog database to UDDF.

 * http://gdivelog.sourceforge.net/
 * http://www.streit.cc/extern/uddf_v300/en/index.html

Requires:

 * SQLAlchemy (http://www.sqlalchemy.org/)

"""

import sys
import os.path
from datetime import datetime, timedelta
from optparse import OptionParser
import xml.dom.minidom
from gdivelog.db import GDiveLogDB
from gdivelog.db import GDiveLogDB
from gdivelog.prefs import GDiveLogPreferences

__author__ = "Eskil Heyn <eskil@eskil.org>"
__maintainer__ = "Eskil Olsen <eskil@eskil.org>"
__copyright__ = "Copyright 2011"
__license__ = "Public Domain"
__version__ = "1.0"
__status__ = "Production"

NAME = 'gdivelog2uddf'
VERSION = '1.0'
# If the Surface Interval is GE this value, it's considered to be infinite long (ie. "clear").
SI_INF = timedelta(days=5)


def celcius_to_kelvin(celcius):
    '''Convert a temperature from C to K'''
    return celcius + 273.15;


def celcius_to_fahrenheit(celcius):
    '''Convert a temperature from C to F'''
    return ((celcius * 9) / 5) + 32


def _xml_add(top, node, tag, text=None, subfields={}, attr={}):
    """
    Helper method to add data to an XML file.

    Args;
       top -- the root for the document
       node -- the node at which to attach the tag under
       tag -- the tag to add
       text -- optional text field for the tag
       subfields -- dictionary of subfields to add, where the key will be the tag name and the value will be the text.
       attr -- dictionary of attributes to add as key=val elements.

    Returns;
       the created element
    """
    element = top.createElement(tag)

    for k, v in attr.iteritems():
        element.setAttribute(k, '%r' % v)

    if text is not None:
        textelement = top.createTextNode('%s' % text)
        element.appendChild(textelement)

    node.appendChild(element)

    for k, v in subfields.iteritems():
        _xml_add(top, element, k, text=v)

    return element


class GDiveLog(object):
    """
    Access GDivelog data.
    """


    class UDDF(object):
        """
        Represent a GDivelog database as a UDDF document.
        """

        def __init__(self, options, preferences):
            self.options = options
            self.preferences = preferences
            self.top = xml.dom.minidom.Document()
            # Put in the <generator> header.
            self.doc = self._add(self.top, 'uddf', attr={'version': '3.0.0',
                                                         'type': 'converter'})
            generator = self._add(self.doc, 'generator', subfields={'name': NAME,
                                                                    'version': VERSION})
            manufacturer = self._add(generator, 'manufacturer', subfields={'name': 'Eskil Heyn Olsen'})
            contact = self._add(manufacturer, 'contact')
            self._add(contact, 'homepage', 'http://github.com/eskilolsen/gdivelog2uddf')
            self._add(contact, 'homepage', 'http://eskil.org/')
            self._add(generator, 'datetime', datetime.now().isoformat())


        def _add(self, node, tag, text=None, subfields={}, attr={}):
            '''Helper function to add tag to node via _xml_add'''
            return _xml_add(self.top, node, tag, text=text, subfields=subfields, attr=attr)


        def _add_text_paragraphs(self, node, tag, text):
            """
            Add a text paragraph to 'node' under the tag 'tag'.
            The given text is split at newlines.
            """
            if not text:
                return
            group = self._add(node, tag)
            for line in text.split('\n'):
                self._add(group, 'para', text=line)


        def add_divers(self, divelog):
            """
            Add the divelog owner and all known buddies to the UDDF document.
            """
            divers = self._add(self.doc, 'diver')
            owner = self._add(divers, 'owner', attr={'id': 'diver_id_0'})
            self._add(owner, 'personal', subfields={'firstname': 'Your First Name', 'lastname': 'Your Last Name'})
            for buddy in divelog.buddies():
                buddy_group = self._add(divers, 'buddy', attr={'id': 'dive_buddy_%d' % buddy.buddy_id})
                names = buddy.buddy_name.split(' ')
                self._add(buddy_group, 'personal', subfields={'firstname': names[0], 'lastname': ' '.join(names[1:])})


        def add_sites(self, divelog):
            """
            Add all known sites to the UDDF document.

            The GDivelog "tree" is lost, since each divesite is formed
            by walking the list of parents and combining using the
            site name seperator.
            """
            divesites = self._add(self.doc, 'divesite')
            for site in divelog.sites():
                site_group = self._add(divesites, 'site', subfields={'name': '/'.join(divelog.site_name_list(site))}, attr={'id': 'dive_site_%d' % site.site_id})


        def add_dives(self, divelog):
            """
            Add all known dives to the UDDF document.
            """
            profiles = self._add(self.doc, 'profiledata')
            previous_divetime = datetime.min

            for dive in divelog.dives():
                # Compute the SI and start a new group if INF
                divetime = datetime.strptime(dive.dive_datetime, '%Y-%m-%d %H:%M:%S')
                surfaceinterval = divetime - previous_divetime
                if surfaceinterval >= SI_INF:
                    group = self._add(profiles, 'repetitiongroup')

                dive_group = self._add(group, 'dive')
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

                if dive.site_id > 0:
                    self._add(dive_group, 'link', attr={'ref': 'dive_site_%d' % dive.site_id})

                for buddy in divelog.buddies(diveid=dive.dive_id):
                    self._add(dive_group, 'link', attr={'ref': 'dive_buddy_%d' % buddy.buddy_id})

                sample_group = self._add(dive_group, 'samples')
                for sample in divelog.samples(dive.dive_id):
                    waypoint = self._add(sample_group, 'waypoint', subfields={'divetime': sample.profile_time,
                                                                              'depth': sample.profile_depth})
                    k = celcius_to_kelvin(sample.profile_temperature)
                    if k > 0:
                        self._add(waypoint, 'temperature', k)

                previous_divetime = divetime


    class UDCF(object):
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
            '''Helper function to add tag to node via _xml_add'''
            return _xml_add(self.top, node, tag, text=text, subfields=subfields, attr=attr)


        def add_dives(self, divelog, args):
            """
            Add all known dives to the UDDF document.
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


    @classmethod
    def db_to_uddf(cls, options, args):
        """
        Convert a GDivelog db into a UDDF document.
        """
        preferences = GDiveLogPreferences(options)
        db = GDiveLogDB(options, preferences)
        uddf = GDiveLog.UDDF(options, preferences)
        uddf.add_divers(db)
        uddf.add_sites(db)
        uddf.add_dives(db)
        return uddf


    @classmethod
    def db_to_udcf(cls, options, args):
        """
        Convert a GDivelog db into a UDCF document.
        """
        preferences = GDiveLogPreferences(options)
        db = GDiveLogDB(options, preferences)
        udcf = GDiveLog.UDCF(options, preferences)
        udcf.add_dives(db, args)
        return udcf


def main(options, args):
    if options.udcf:
        xml = GDiveLog.db_to_udcf(options, args)
    else:
        xml = GDiveLog.db_to_uddf(options, args)

    if options.output:
        out = open(options.output, 'w')
    else:
        out = sys.stdout

    if options.prettyprint:
        out.write(xml.doc.toprettyxml())
    else:
        xml.doc.writexml(out)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-d', '--dir', dest='gdivelog_dir', default=os.path.expanduser('~/.gdivelog'),
                      help='Directory with gdivelog "lastopened" and "preferences"')
    parser.add_option('-i', '--input', dest='gdivelog_db', metavar='FILE', default=None, help='gdivelog log file')
    parser.add_option('-c', '--config', dest='gdivelog_preferences', default=None, help='gdivelog preferences file')

    parser.add_option('-p', '--pretty-print', '--pretty', '--prettyprint', action='store_true', dest='prettyprint', default=False, help='pretty print xml')
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose', default=False,  help='print status messages to stdout')
    parser.add_option('-u', '--udcf', action='store_true', dest='udcf', default=False, help='dump dives as udcf')
    parser.add_option('-o', '--output', dest='output', default=None, help='Output filename. Must be set if using --segment')
    parser.add_option('--trip-threshold', dest='trip_threshold', default=None, help='Dives within this number of days are grouped into 1 trip')
    parser.add_option('--segment', dest='segment_size', default=None, help='To reduce memory usage, batch output into files with this number of dives per segment (number will be varied since trips will not be split')

    (options, args) = parser.parse_args()

    if not options.gdivelog_preferences:
        options.gdivelog_preferences = options.gdivelog_dir + '/preferences'

    if not options.gdivelog_db:
        lastopened = open(options.gdivelog_dir + '/lastopened', 'r')
        options.gdivelog_db = lastopened.read()

    main(options, args)
