# −*− coding: UTF−8 −*−
from django.db.models.base import ModelBase
import datetime
from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _
import sys
from occurrencegenerators import *
from occurrences import *
from utils import occurrences_to_events
from eventtools.deprecated import deprecated
from dynamicmodel import create_model_for_module
from eventtools.periods import Period

from django.core.exceptions import ValidationError

"""
When you subclass EventBase (further down), two more models are injected into your app by EventModelBase (just below).

Say your EventBase subclass is called Lecture. You will get LectureOccurrenceGenerator and LectureOccurrence models. Briefly, OccurrenceGenerators generate Occurrences. Occurrences are saved to the database and retrieved from the database if they contain differences to the Occurrence values.

See occurrencegenerators.py and occurrences.py for details.

How to use EventBase:

Every EventBase model has several OccurrenceGenerators, each of which generate several Occurrences (and save the interesting ones to the database).

You can get the OccurrenceGenerators with Event.generators (it's the reverse relation name).

Since OccurrenceGenerators can generate a potentially infinite number of occurrences, you don't want to be able to get all the occurrences ever (it would take a while). You can tell whether an event has infinite amount of occurrences by seeing whether Event.get_last_day() returns a value. If it returns False, there's no end.

To get an Event's occurrences between two dates:

Event.occurrences_between(start_datetime, end_datetime).

This will return a list of EventOccurrences. Remember to use EventOccurrence.merged_event to display the details for each event (since merged_event takes in to account variations).

"""

class EventQuerySetBase(models.query.QuerySet):
    def occurrences_between(self, start, end, hide_hidden=True):        
        """
        returns the EventOccurrences in a given date(datetime) range.
        """
        if hide_hidden:
            return Period(self, start, end).get_occurrences()
        else:
            return Period(self, start, end).get_even_hidden_occurrences()
            
        return sorted(occurrences)

    def between(self, start, end, hide_hidden=True):
        """
        returns the Events (not occurrences) that occur in a given datetime range
        """
        occurrences = self.occurrences_between(start, end)
        return occurrences_to_events(occurrences)

    @deprecated
    def occurrences_between_days(self, startday, endday, hide_hidden=True):
        return self.occurrences_between(startday, endday, hide_hidden)

    @deprecated
    def between_days(self, startday, endday, hide_hidden=True):
        return self.between(startday, endday, hide_hidden)

    @deprecated
    def occurrences_on_day(self, day, hide_hidden=True):
        "Shortcut method"
        return self.occurrences_between_days(day, day, hide_hidden) 

    @deprecated
    def on_day(self, day, hide_hidden=True):
        occurrences = self.occurrences_on_day(day, hide_hidden)
        return occurrences_to_events(occurrences)


class EventManagerBase(models.Manager):
    def get_query_set(self): 
        return EventQuerySetBase(self.model)
        
    def occurrences_between(self, start, end, hide_hidden=True):
        return self.get_query_set().occurrences_between(start, end, hide_hidden)
        
    def between(self, start, end, hide_hidden=True):
         return self.get_query_set().between(start, end, hide_hidden)
    
    @deprecated     
    def occurrences_between_days(self, startday, endday, hide_hidden=True):
         return self.get_query_set().occurrences_between_days(startday, endday, hide_hidden)

    @deprecated
    def between_days(self, startday, endday, hide_hidden=True):
         return self.get_query_set().between_days(startday, endday, hide_hidden)
         
    @deprecated
    def occurrences_on_day(self, day, hide_hidden=True):
        return self.get_query_set().on_day(day, hide_hidden)

    @deprecated
    def on_day(self, day, hide_hidden=True):
        return self.get_query_set().on_day(day, hide_hidden)


class EventModelBase(ModelBase):
    def __init__(cls, name, bases, attrs):
        """
        Dynamically generate two related classes to handle occurrences (get the vodka out, George).
        
        The two generated classes are ModelNameOccurrence and ModelNameOccurrenceGenerator.        
        """
        
        
        if name != 'EventBase': # This should only fire if this is a subclass (maybe we should make devs apply this metaclass to their subclass instead?)
            # Build names for the new classes
            occ_name = "%s%s" % (name, "Occurrence")
            gen_name = "%s%s" % (occ_name, "Generator")
            
            generator_fields = {
                    '__module__': cls.__module__,
                    'event': models.ForeignKey(cls, related_name = 'generators'),
                    '_occurrence_model_name': occ_name,
                }
            gen_model = create_model_for_module(gen_name, cls.__module__, generator_fields, (OccurrenceGeneratorBase,))
           
            occurrence_fields = {
                '__module__': cls.__module__,
                'generator': models.ForeignKey(gen_name, related_name = 'occurrences'),
            }
            if hasattr(cls, 'varied_by'):
                occurrence_fields['_varied_event'] = models.ForeignKey(cls.varied_by, related_name = 'occurrences', null=True,blank=True,help_text=_("Create or add a variation to alter venue, price, description, etc..."))
                # we need to add an unvaried_event FK into the variation class, BUT at this point the
                # variation class hasn't been defined yet. For now, let's insist that this is done by
                # using a base class for variation.      
            occ_model = create_model_for_module(occ_name, cls.__module__, occurrence_fields, (OccurrenceBase,))
                        
            cls.add_to_class('Occurrence', occ_model)
            cls.add_to_class('OccurrenceGenerator', gen_model)         

        super(EventModelBase, cls).__init__(name, bases, attrs)

class EventBase(models.Model):
    """
    Event information minus the scheduling details.
    
    Event scheduling is handled by one or more OccurrenceGenerators
    """
    
    #injected by EventModelBase:
    # Occurrence
    # OccurrenceGenerator
    
    __metaclass__ = EventModelBase
    _date_description = models.TextField(_("Describe when this event occurs"), blank=True, help_text=_("e.g. \"Every Tuesday and Thursday in March 2010\". If this is omitted, an automatic description will be attempted."))
    
    objects = EventManagerBase()
    
    class Meta:
        abstract = True

    def clean(self):
        """
        validation:
        if there are variations, throw a validation error.
        (otherwise, the normal date_description function is used).
        """
        if self.variations_count() > 0 and not self.date_description:
            raise ValidationError("Sorry, we can't figure out how to describe an event with variations. Please add your own date description under Visitor Info.")

    def date_description(self): # Took out hide_hidden - why would you want to hide a generator?
        if self._date_description:
            return self._date_description
        gens = self.generators.all()
        if gens:
            return _("\n ").join([g.date_description() for g in gens])
        else:
            return _("Date TBA")
    date_description = property(date_description)
    
    def _opts(self):
        return self._meta
    opts = property(_opts) #for use in templates (without underscore necessary)

    def _has_zero_generators(self):
        return self.generators.count() == 0
    has_zero_generators = property(_has_zero_generators)
        
    def _has_multiple_occurrences(self):
        return self.generators.count() > 1 or (self.generators.count() > 0 and self.generators.all()[0].rule != None)
    has_multiple_occurrences = property(_has_multiple_occurrences)
    
    def get_first_generator(self):
        return self.generators.order_by('first_start_date', 'first_start_time')[0]
    first_generator = property(get_first_generator)
            
    def get_first_occurrence(self):
        try:
            return self.first_generator.get_first_occurrence()
        except IndexError:
            raise IndexError("This Event type has no generators defined")
    get_one_occurrence = get_first_occurrence # for backwards compatibility
    
    @deprecated
    def get_occurrences(self, start, end, hide_hidden=True):
        return self.occurrences_between(start, end, hide_hidden)
        
    def occurrences_between(self, start, end, hide_hidden=True):
        return self.generators.occurrences_between(start, end, hide_hidden)
        
    def get_all_occurrences_if_possible(self):
        if self.get_last_day():
            return self.occurrences_between(self.first_generator.start, self.get_last_day())
        return None
    
    def occurrences_count(self):
        al = self.get_all_occurrences_if_possible()
        if al:
            return len(list(al))
        else:
            return '&infin;'
    occurrences_count.allow_tags = True
    
    def get_changed_occurrences(self):
        """
        return all the variation occurrences as well as
        the occurences which have changed (different time, date, or cancelled)
        """
        occs = []
        variation_occs = []
        
        # get the variations
        for variation in self.variations.all():
            variation_occs += list(variation.occurrences.all())
        
        # also get the changed occurrences
        for gen in self.generators.all():
            occs += gen.get_changed_occurrences() #wouldn't this always contain variation occurrences?
        
        return list(set(sorted(occs + variation_occs)))
    
    def get_last_occurrence_end(self):
        lastdays = []
        for generator in self.generators.all():
            if generator.repeat_until:
                lastdays.append(generator.repeat_until)
            else:
                if generator.rule:
                    return None
                lastdays.append(generator.end)
            for varied in generator.get_changed_occurrences():
                lastdays.append(varied.varied_end)

        # coerce dates into datetimes (so that sort will work)
        for i, day in enumerate(lastdays):
            if isinstance(day, datetime.date):
                lastdays[i] = datetime.datetime.combine(day, datetime.time(0,0))
                
        lastdays.sort()
        try:
            return lastdays[-1]
        except IndexError:
            return None

    def has_finished(self):
        now = datetime.datetime.now()
        if self.get_last_occurrence_end() < now:
            return True
        return False

    def edit_occurrences_link(self):
        """ An admin link """
        # if self.has_multiple_occurrences:
        if self.has_zero_generators:
            return _('no occurrences yet (<a href="%s/">add a generator here</a>)' % self.id)
        else:
           return '<a href="%s/occurrences/">%s</a>' % (self.id, unicode(_("view/edit occurrences")))
    edit_occurrences_link.allow_tags = True
    edit_occurrences_link.short_description = _("Occurrences")
    
    def variations_count(self):
        """
        returns the number of variations that this event has
        """
        if hasattr(type(self), 'varied_by'):
            try:
                return self.variations.count()
            except: # if none have been created, there is no such thing as self.variations, so return 0
                return 0
        else:
            return "N/A"  
    variations_count.short_description = _("# Variations")
    
    def create_generator(self, *args, **kwargs):
        #for a bit of backwards compatibility. If you provide two datetimes, they will be split out into dates and times.
        if kwargs.has_key('start'):
            start = kwargs.pop('start')
            kwargs.update({
                'first_start_date': start.date(),
                'first_start_time': start.time()
            })
        if kwargs.has_key('end'):
            end = kwargs.pop('end')
            kwargs.update({
                'first_end_date': end.date(),
                'first_end_time': end.time()
            })
        repeat_until = kwargs.get('repeat_until')
        if repeat_until and isinstance(repeat_until, datetime.date):
            kwargs['repeat_until'] = datetime.datetime.combine(repeat_until, datetime.time.max)

        return self.generators.create(*args, **kwargs)
    
    def create_variation(self, *args, **kwargs):
        kwargs['unvaried_event'] = self
        return self.variations.create(*args, **kwargs)
        
    def next_occurrences(self, num_days=28): #why is this necessary? deprecate in favour of occurrences between day, day+timedelta(28)?
        from eventtools.periods import Period
        first = False
        last = False
        for gen in self.generators.all():
            if not first or gen.start < first:
                first = gen.start
            if gen.rule and not gen.repeat_until:
                last = False # at least one rule is infinite
                break
            if not gen.repeat_until:
                genend = gen.start
            else:
                genend = gen.repeat_until
            if not last or genend > last:
                last = genend
        if last:
            period = Period(self.generators.all(), first, last)
        else:
            period = Period(self.generators.all(), datetime.datetime.now(), datetime.datetime.now() + datetime.timedelta(days=num_days))
        return period.get_occurrences()

    #deprecations
    @deprecated #doesn't work super-well. Just use Occurrence instead.
    def _occurrence_model(self):
        return type(self).Occurrence
    OccurrenceModel = property(_occurrence_model)

    @deprecated
    def _generator_model(self):
        return type(self).OccurrenceGenerator
    GeneratorModel = property(_generator_model)

    @deprecated #badly named
    def get_last_day(self):
        return self.get_last_occurrence_end()
