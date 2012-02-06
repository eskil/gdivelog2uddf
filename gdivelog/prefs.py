"""
Represents the GDivelog preferences file.
"""

import struct


__all__ = ['GDiveLogPreferences']
__author__ = "Eskil Heyn <eskil@eskil.org>"
__maintainer__ = "Eskil Olsen <eskil@eskil.org>"
__copyright__ = "Copyright 2011"
__license__ = "Public Domain"
__version__ = "1.0"
__status__ = "Production"


class GDiveLogPreferences(object):
    """
    Represents the GDivelog preferences file.

    Currently only the depth units and the sitename seperator is supported.
    """

    def __init__(self, options):
        """
        This is the layout of the preferences file ;

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

        And this is what a GdkColor looks like ;

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

        if False:
            # Ideally we'd do this... but the padding seems to be off.
            try:
                (depth_unit, _, _, _, _, _, # units
                 _, _, _, _, # color...
                 _, _, _, _, # color...
                 _, _, _, _, # color...
                 _, _, _, _, # color...
                 _, _, _, _, # color...
                 _, _, _, _, # color...
                 _, _, _,
                 site_name_seperator,
                 _, _,
                 _ # pad to lines of 16b
                 ) = struct.unpack('6cl3hl3hl3hl3hl3hl3h2id4sil8c', data)
            except struct.error, e:
                print 'length of data = %d' % (len(data),)
                raise e
        else:
            # So instead I do this. This is particularly
            # assy since padding can affect 0140.
            (self.depth_unit, _, _, _, _, _) = struct.unpack('@6c', data[0:6])
            self.site_name_seperator = ''.join(struct.unpack('@4c', data[0140:0144])).split('\0')[0]

        self.site_name_seperator = self.site_name_seperator.split('\0')[0]
