import datetime

from django.db import models
from django.utils.translation import ugettext as _
from eventtools.utils import datetimeify
from eventtools.utils.pprint_timespan import pprint_datetime_span, pprint_time_span
from django.utils.safestring import mark_safe

class XTimespanModel(models.Model):
    start = models.DateTimeField(db_index=True)
    _duration = models.PositiveIntegerField(_("duration (mins)"), blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ('start', )

    def get_duration(self):
        """
        _duration is a value in minutes. The duration property returns a timedelta representing this.
        """
        if self._duration:
            return datetime.timedelta(seconds = self._duration * 60)
        else:
            return datetime.timedelta(0)

    def set_duration(self, v):
        """
        Pass in a timedelta to convert to minutes; pass in something else to set directly.
        """
        if isinstance(v, datetime.timedelta):
            self._duration = v.days * 24 * 60 + v.seconds / 60
        else:
            self._duration = v

    duration = property(get_duration, set_duration)

    def end(self):
        return self.start + self.duration

    def all_day(self):
        """
        WARNING: the implementation of 'all day' may change, for example by making it a BooleanField. If this is important to you, define it yourself.

        By default, an event is 'all day' if the start time is time.min (ie midnight) and the duration is not provided.

        'All day' is distinguished from events that last 24 hours, because there is a reader assumption that opening hours are taken into account.

        Implementers may prefer their own definition, maybe adding a BooleanField that overrides the given times.
        """
        return self.start.time() == datetime.time.min and not self._duration

    def timespan_description(self, html=False):
        if html:
            return mark_safe(pprint_datetime_span(self.start, self.end(),
                infer_all_day=False,
                space="&nbsp;",
                date_range_str="&ndash;",
                time_range_str="&ndash;",
                separator=":",
                grand_range_str="&nbsp;&ndash;&nbsp;",
            ))
        return mark_safe(pprint_datetime_span(self.start, self.end(), infer_all_day=False))

    def html_timespan(self):
        return self.timespan_description(html=True)

    def time_description(self, html=False):
#        if self.all_day():
#            return mark_safe(_("all day"))

        t1 = self.start.time()
        if self.start.date() == self.end.date():
            t2 = self.end.time()
        else:
            t2 = t1

        if html:
            return mark_safe(pprint_time_span(t1, t2, range_str="&ndash;&#8203;"))
        return pprint_time_span(t1, t2)

    def html_time_description(self):
        return self.time_description(html=True)

    def has_finished(self):
        return self.end() < datetime.datetime.now()

    def has_started(self):
        return self.start < datetime.datetime.now()

    def now_on(self):
        return self.has_started() and not self.has_finished()

    def time_to_go(self):
        """
        If self is in future, return + timedelta.
        If self is in past, return - timedelta.
        If self is now on, return timedelta(0)
        """
        if not self.has_started():
            return self.start - datetime.datetime.now()
        if self.has_finished():
            return self.end() - datetime.datetime.now()
        return datetime.timedelta(0)

    def start_date(self):
        """Used for regrouping in template"""
        return self.start.date()

    def humanised_day(self):
        if self.start.date() == datetime.date.today():
            return _("Today")
        elif self.start.date() == datetime.date.today() + datetime.timedelta(days=1):
            return _("Tomorrow")
        elif self.start.date() < datetime.date.today() + datetime.timedelta(days=7):
            return format(self.start, "l")
        else:
            return format(self.start, "m d")

"""
TODO:

timespan +/ timedelta = new timespan
"""