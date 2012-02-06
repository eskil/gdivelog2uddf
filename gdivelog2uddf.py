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
from gdivelog.uddf import GDiveLogUDDF

__author__ = "Eskil Heyn <eskil@eskil.org>"
__maintainer__ = "Eskil Olsen <eskil@eskil.org>"
__copyright__ = "Copyright 2011"
__license__ = "Public Domain"
__version__ = "1.0"
__status__ = "Production"


def gdivelog_to_uddf(options, args):
    """
    Convert a GDivelog db into a UDDF document.
    Returns;
       a GDiveLogUDDF object which has a doc property that is the xml.
    """
    preferences = GDiveLogPreferences(options)
    db = GDiveLogDB(options, preferences)
    uddf = GDiveLogUDDF(db, options, preferences, args)
    uddf.add_divers()
    uddf.add_sites()
    uddf.add_divetrips()
    uddf.add_dives()
    return uddf


def gdivelog_to_udcf(options, args):
    """
    Convert a GDivelog db into a UDCF document.
    Returns;
       a GDiveLogUDCF object which has a doc property that is the xml.
    """
    preferences = GDiveLogPreferences(options)
    db = GDiveLogDB(options, preferences)
    udcf = GDiveLog.UDCF(options, preferences)
    udcf.add_dives(db, args)
    return udcf


def main(options, args):
    if options.udcf:
        xml = gdivelog_to_udcf(options, args)
    else:
        xml = gdivelog_to_uddf(options, args)

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
    parser.add_option('--trip-threshold', dest='trip_si_threshold', type='int', default=None, help='Dives within this number of days are grouped into 1 trip')
    #parser.add_option('--segment', dest='segment_size', default=None, help='To reduce memory usage, batch output into files with this number of dives per segment (number will be varied since trips will not be split')

    (options, args) = parser.parse_args()

    if not options.gdivelog_preferences:
        options.gdivelog_preferences = options.gdivelog_dir + '/preferences'

    if not options.gdivelog_db:
        lastopened = open(options.gdivelog_dir + '/lastopened', 'r')
        options.gdivelog_db = lastopened.read()

    main(options, args)
