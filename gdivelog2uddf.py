"""

Convert gdivelog database to UDDF.

 * http://gdivelog.sourceforge.net/
 * http://www.streit.cc/extern/uddf30zeta/en/index.html

Requires:

 * SQLAlchemy (http://www.sqlalchemy.org/)

"""

import sys
import os.path
import struct
import tempfile
import bz2
from datetime import datetime, timedelta
from optparse import OptionParser
import xml.dom.minidom
import sqlite3
import sqlalchemy
import sqlalchemy.ext.declarative
from sqlalchemy import Table, Column, Integer, Float, String, MetaData, ForeignKey

Base = sqlalchemy.ext.declarative.declarative_base()
NAME = 'gdivelog2uddf'
VERSION = '1.0'
SI_INF = timedelta(days=5)


def celcius_to_kelvin(celcius):
	return celcius + 273.15;


def celcius_to_fahrenheit(celcius):
	return ((celcius * 9) / 5) + 32


def xml_add(top, node, tag, text=None, subfields={}, attr={}):
	element = top.createElement(tag)
	
	for k, v in attr.iteritems():
		element.setAttribute(k, '%r' % v)
		
	if text is not None:
		textelement = top.createTextNode('%s' % text)
		element.appendChild(textelement)

	node.appendChild(element)		

	for k, v in subfields.iteritems():
		xml_add(top, element, k, text=v)

	return element


class GDiveLog(object):
	""" """


	class Preferences(object):
		""" """

		def __init__(self, options):
			"""
			  gchar depth_unit;             /* m = meters, anything else feet is assumed          */
			  gchar temperature_unit;       /* c = centigrade, anything else farenheit is assumed */
			  gchar weight_unit;            /* l = lbs, anything else Kgs is assumed              */
			  gchar pressure_unit;          /* b = bar, anything else psi is assumed              */
			  gchar volume_unit;            /* l = liter, anything else cuft is assumed           */
			  gchar profile_max_ascent_rate;            /* In meters. Do not show alarms  <=0                 */

			  GdkColor profile_depth_color;
			  GdkColor profile_temperature_color;
			  GdkColor profile_marker_color;
			  GdkColor profile_background_color;
			  GdkColor profile_alarm_color;
			  GdkColor profile_text_axis_color;

			  gint merge_variance;
			  gint match_variance;
			  gdouble split_dive_limit;

			  gchar site_name_seperator[4];
			  gboolean allow_deletes;
			  glong template_dive_number;

			  struct _GdkColor
			  {
			  guint32 pixel;
			  guint16 red;
			  guint16 green;
			  guint16 blue;
			  };
			  """
			preferences = open(options.gdivelog_preferences, 'rb')
			data = preferences.read()

			# Ideally we'd do this... but the padding seems to be off.

			#(depth_unit, _, _, _, _, _, # units
			# _, _, _, _, # color...
			# _, _, _, _, # color...
			# _, _, _, _, # color...
			# _, _, _, _, # color...
			# _, _, _, _, # color...
			# _, _, _, _, # color...
			# _, _, _, 
			# site_name_seperator,
			# _, _) = struct.unpack('@6cl3hl3hl3hl3hl3hl3h2id4sil', data)

			# So instead I do this assy shit. This is particularly
			# assy since padding can affect 0140.
			(self.depth_unit, _, _, _, _, _) = struct.unpack('@6c', data[0:6])
			self.site_name_seperator = ''.join(struct.unpack('@4c', data[0140:0144])).replace('\0', '')


	class DB(object):
		"""SQLAlchemy ORM for gdivelogs sqlite db"""


		def __init__(self, options, preferences):
			""" """
			self.preferences = preferences
			self.bunzipped2 = tempfile.NamedTemporaryFile(delete=True)
			for data in bz2.BZ2File(options.gdivelog_db):
				self.bunzipped2.write(data)
			self.bunzipped2.flush()

			engine = sqlalchemy.create_engine('sqlite:///%s' % self.bunzipped2.name, echo=options.verbose) 
			Session = sqlalchemy.orm.sessionmaker(bind=engine)
			self.session = Session()


		class Site(Base):
			__tablename__ = 'Site'
			site_id = Column(Integer, primary_key=True)
			site_parent_id = Column(Integer, ForeignKey('Site.site_id'))
			site_name = Column(String)
			site_notes = Column(String)			


		class Dive(Base):
			__tablename__ = 'Dive'
			dive_id = Column(Integer, primary_key=True)
			dive_number = Column(Integer)
			dive_datetime = Column(String)
			dive_duration = Column(Integer)
			dive_maxdepth = Column(Float)
			dive_mintemp = Column(Float)
			dive_maxtemp = Column(Float)
			dive_notes = Column(String)
			site_id = Column(Integer, ForeignKey('Site.site_id'))
			dive_visibility = Column(Float)
			dive_weight = Column(Float)


		class Profile(Base):
			__tablename__ = 'Profile'
			dive_id = Column(Integer, ForeignKey('Dive.dive_id'), primary_key=True)
			profile_time = Column(Integer, primary_key=True)
			profile_depth = Column(Float)
			profile_temperature = Column(Float)


		class Buddy(Base):
			__tablename__ = 'Buddy'
			buddy_id = Column(Integer, primary_key=True)
			buddy_name = Column(String)
			buddy_notes = Column(String)


		class DiveBuddy(Base):
			__tablename__ = 'Dive_Buddy'
			dive_id = Column(Integer, primary_key=True)
			buddy_id = Column(Integer, primary_key=True)


		def dives(self, numbers=[]):			
			if numbers == []:
				query = self.session.query(GDiveLog.DB.Dive).order_by(GDiveLog.DB.Dive.dive_number.asc())
			else:
				query = self.session.query(GDiveLog.DB.Dive).filter(GDiveLog.DB.Dive.dive_number == 124).order_by(GDiveLog.DB.Dive.dive_number.asc())
				
			for dive in query:
				yield dive


		def buddies(self):
			for buddy in self.session.query(GDiveLog.DB.Buddy):
				yield buddy


		def dive_buddies(self, diveid):
			for buddy in self.session.query(GDiveLog.DB.DiveBuddy).filter(GDiveLog.DB.DiveBuddy.dive_id == diveid):
				yield buddy


		def samples(self, diveid):
			for sample in self.session.query(GDiveLog.DB.Profile).filter(GDiveLog.DB.Profile.dive_id == diveid).order_by(GDiveLog.DB.Profile.profile_time.asc()):
				yield sample


		def sites(self):
			for site in self.session.query(GDiveLog.DB.Site):
				yield site


		def site_name_list(self, site):
			"""Recursively find site parents and return the list of [Parent, Parent..., Child]"""
			result = []
			if site.site_parent_id > 0:
				parent_site = self.session.query(GDiveLog.DB.Site).filter(GDiveLog.DB.Site.site_id == site.site_parent_id).one()
				result = self.site_name_list(parent_site)
				result.append(site.site_name)
			return result


		def site_name(self, siteid):
			site = self.session.query(GDiveLog.DB.Site).filter(GDiveLog.DB.Site.site_id == siteid).one()
			return self.preferences.site_name_seperator.join(self.site_name_list(site))

	class UDDF(object):


		def __init__(self, preferences):
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
			return xml_add(self.top, node, tag, text=text, subfields=subfields, attr=attr)


		def _add_text_paragraphs(self, node, tag, text):
			if not text:
				return
			group = self._add(node, tag)
			for line in text.split('\n'):
				self._add(group, 'para', text=line)


		def add_divers(self, divelog):
			divers = self._add(self.doc, 'diver')
			owner = self._add(divers, 'owner', attr={'id': 'diver_id_0'})
			self._add(owner, 'personal', subfields={'firstname': 'Your First Name', 'lastname': 'Your Last Name'})
			for buddy in divelog.buddies():
				buddy_group = self._add(divers, 'buddy', attr={'id': 'dive_buddy_%d' % buddy.buddy_id})
				names = buddy.buddy_name.split(' ')
				self._add(buddy_group, 'personal', subfields={'firstname': names[0], 'lastname': ' '.join(names[1:])})


		def add_sites(self, divelog):
			divers = self._add(self.doc, 'divesite')
			for site in divelog.sites():
				site_group = self._add(self.doc, 'site', subfields={'name': '/'.join(divelog.site_name_list(site))}, attr={'id': 'dive_site_%d' % site.site_id})


		def add_dives(self, divelog):
			profiles = self._add(self.doc, 'profiledata')
			previous_divetime = datetime.min

			for dive in divelog.dives():
				# Compute the SI and start a new group if INF
				divetime = datetime.strptime(dive.dive_datetime, '%Y-%m-%d %H:%M:%S')
				surfaceinterval = divetime - previous_divetime			
				if surfaceinterval > SI_INF:
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

				for buddy in divelog.dive_buddies(dive.dive_id):
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


		def __init__(self, preferences):
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
			return xml_add(self.top, node, tag, text=text, subfields=subfields, attr=attr)


		def add_dives(self, divelog, args):
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
		preferences = GDiveLog.Preferences(options)
		db = GDiveLog.DB(options, preferences)
		uddf = GDiveLog.UDDF(preferences)
		uddf.add_divers(db)
		uddf.add_sites(db)
		uddf.add_dives(db)
		return uddf


	@classmethod
	def db_to_udcf(cls, options, args):
		preferences = GDiveLog.Preferences(options)
		db = GDiveLog.DB(options, preferences)
		udcf = GDiveLog.UDCF(preferences)
		udcf.add_dives(db, args)
		return udcf


def main(options, args):
	if options.udcf:
		xml = GDiveLog.db_to_udcf(options, args)
	else:
		xml = GDiveLog.db_to_uddf(options, args)

	if options.prettyprint:
		print xml.doc.toprettyxml()
	else:
		xml.doc.writexml(sys.stdout)


if __name__ == '__main__':
	parser = OptionParser()
	parser.add_option('-d', '--dir', dest='gdivelog_dir', default=os.path.expanduser('~/.gdivelog'),
					  help='Directory with gdivelog "lastopened" and "preferences"')
	parser.add_option('-f', '--file', dest='gdivelog_db', metavar='FILE', default=None, help='gdivelog log file')
	parser.add_option('-c', '--config', dest='gdivelog_preferences', default=None, help='gdivelog preferences file')

	parser.add_option('-p', '--pretty-print', action='store_true', dest='prettyprint', default=False, help='pretty print xml')
	parser.add_option('-v', '--verbose', action='store_true', dest='verbose', default=False,  help='print status messages to stdout')	
	parser.add_option('-u', '--udcf', action='store_true', dest='udcf', default=False, help='dump dives as udcf')
	(options, args) = parser.parse_args()

	if not options.gdivelog_preferences:
		options.gdivelog_preferences = options.gdivelog_dir + '/preferences'

	if not options.gdivelog_db:
		lastopened = open(options.gdivelog_dir + '/lastopened', 'r')
		options.gdivelog_db = lastopened.read()

	main(options, args)
