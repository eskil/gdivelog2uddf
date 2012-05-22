"""
SQLAlchemy ORM for gdivelog's sqlite db
"""

import tempfile
import bz2
import sqlalchemy
import sqlalchemy.ext.declarative
from sqlalchemy import Table, Column, Integer, Float, String, MetaData, ForeignKey


__all__ = ['GDiveLogDB']
__author__ = "Eskil Heyn <eskil@eskil.org>"
__maintainer__ = "Eskil Olsen <eskil@eskil.org>"
__copyright__ = "Copyright 2011"
__license__ = "Public Domain"
__version__ = "1.0"
__status__ = "Production"


class GDiveLogDB(object):
    """
    SQLAlchemy ORM for gdivelog's sqlite db
    """

    Base = sqlalchemy.ext.declarative.declarative_base()

    def __init__(self, options, preferences):
        """
        """
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
        # Relate dives to buddies
        __tablename__ = 'Dive_Buddy'
        dive_id = Column(Integer, ForeignKey('Dive.dive_id'), primary_key=True)
        buddy_id = Column(Integer, ForeignKey('Buddy.buddy_id'), primary_key=True)


    class Equipment(Base):
        __tablename__ = 'Equipment'
        equipment_id = Column(Integer, primary_key=True)
        equipment_name = Column(String)
        equipment_notes = Column(String)


    class DiveEquipment(Base):
        # Relate dives to equipment
        __tablename__ = 'Dive_Equipment'
        equipment_id = Column(Integer, ForeignKey('Equipment.equipment_id'), primary_key=True)
        dive_id = Column(Integer, ForeignKey('Dive.dive_id'), primary_key=True)


    class Tank(Base):
        __tablename__ = 'Tank'
        tank_id = Column(Integer, primary_key=True)
        tank_name = Column(String)
        tank_volume = Column(Float)
        tank_wp = Column(Float)
        tank_notes = Column(String)


    class DiveTank(Base):
        # Relate dives to tanks and their usage
        __tablename__ = 'Dive_Tank'
        dive_tank_id = Column(Integer, primary_key=True)
        dive_id = Column(Integer, ForeignKey('Dive.dive_id'))
        tank_id = Column(Integer, ForeignKey('Tank.tank_id'))
        dive_tank_avg_depth = Column(Float)
        dive_tank_O2 = Column(Float)
        dive_tank_He = Column(Float)
        dive_tank_stime = Column(Integer)
        dive_tank_etime = Column(Integer)
        dive_tank_spressure = Column(Float)
        dive_tank_epressure = Column(Float)


    def dives(self, numbers=[]):
        """
        Generator to iterate across dives in the database. Optionally only iterate across the ones listed in numbers.
        """
        if numbers == []:
            query = self.session.query(GDiveLogDB.Dive).order_by(GDiveLogDB.Dive.dive_number.asc())
        else:
            query = self.session.query(GDiveLogDB.Dive).filter(GDiveLogDB.Dive.dive_number.in_(numbers)).order_by(GDiveLogDB.Dive.dive_number.asc())

        for dive in query:
            yield dive


    def dive_by_id(self, diveid):
        return self.session.query(GDiveLogDB.Dive).filter(GDiveLogDB.Dive.dive_id == diveid).one()


    def equipment(self, diveid=None):
        """
        Generator to iterate across equipment
        """
        if diveid:
            query = self.session.query(GDiveLogDB.DiveEquipment).filter(GDiveLogDB.DiveEquipment.dive_id == diveid)
        else:
            query = self.session.query(GDiveLogDB.Equipment)

        for equipment in query:
            yield equipment

    def buddies(self, diveid=None):
        """
        Generator to iterate across buddies in the database.
        Optionally list buddies for a particular dive.
        """
        if not diveid:
            for buddy in self.session.query(GDiveLogDB.Buddy):
                yield buddy
        else:
            for buddy in self.session.query(GDiveLogDB.DiveBuddy).filter(GDiveLogDB.DiveBuddy.dive_id == diveid):
                yield buddy


    def samples(self, diveid):
        """
        Generator to iterate across waypoint samples for a dive
        """
        for sample in self.session.query(GDiveLogDB.Profile).filter(GDiveLogDB.Profile.dive_id == diveid).order_by(GDiveLogDB.Profile.profile_time.asc()):
            yield sample


    def dive_tanks(self, diveid=None):
        query = self.session.query(GDiveLogDB.DiveTank)
        if diveid:
            query = query.filter(GDiveLogDB.DiveTank.dive_id == diveid)
        for dive_tank in query:
            yield dive_tank


    def tanks(self):
        for tank in self.session.query(GDiveLogDB.Tank):
            yield tank


    def tank_by_id(self, tankid):
        return self.session.query(GDiveLogDB.Tank).filter(GDiveLogDB.Tank.tank_id == tankid).one()


    def sites(self):
        """
        Generator to iterate across dive sites.

        Note, the site entries themselves are just fragments of
        the entire site name. See site_name_list and site_name.
        """
        for site in self.session.query(GDiveLogDB.Site):
            yield site


    def site_name_list(self, site):
        """
        Recursively find site parents and return the list of [Parent, Parent..., Child]
        """
        result = []
        if site.site_parent_id > 0:
            parent_site = self.session.query(GDiveLogDB.Site).filter(GDiveLogDB.Site.site_id == site.site_parent_id).one()
            result = self.site_name_list(parent_site)
            result.append(site.site_name)
        return result


    def site_name(self, siteid):
        """
        Returns a sitename given the siteid. Uses site_name_list to find all the parents.
        """
        site = self.session.query(GDiveLogDB.Site).filter(GDiveLogDB.Site.site_id == siteid).one()
        return self.preferences.site_name_seperator.join(self.site_name_list(site))

