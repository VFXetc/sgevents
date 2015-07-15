import json


def _item_property(key, doc=None, transform=None):
    if transform:
        def _func(event):
            return transform(event.get(key))
    else:
        def _func(event):
            return event.get(key)
    return property(_func, doc=doc)


_specialization_classes = {}

def _specialization(subtype, entity_type=None, domain='Shotgun'):
    def _decorator(cls):
        _specialization_classes[(domain, entity_type, subtype)] = cls
        return cls
    return _decorator



class Event(dict):

    """A smarter ``EventLogEntry`` entity.

    This is a dict, just as would be returned from the Shotgun API, but it
    is instrumented with a number of properties and methods to smooth out
    some of the edge cases of the event log.

    """

    #: Required fields to query from the API.
    return_fields = (
        'attribute_name',
        'created_at',
        'entity',
        'event_type',
        'meta',
        'project',
        'user',
    )
    
    @classmethod
    def factory(cls, event):
        domain, entity_type, subtype = event['event_type'].split('_', 2)
        subcls = (
            _specialization_classes.get((domain, entity_type, subtype)) or 
            _specialization_classes.get((domain, None       , subtype)) or
            cls
        )
        return subcls(event)

    def __init__(self, raw, shotgun=None):
        super(Event, self).__init__(raw)
        self._shotgun = shotgun

    id = _item_property('id', """The ID of the ``EventLogEntry`` entity.""")

    created_at = _item_property('created_at',
        """When the event happened, in the type returned by the Shotgun API object.""")

    type = _item_property('event_type',
        """The complete type of the event, e.g. ``"Shotgun_Shot_Change"``.""")

    domain = _item_property('event_type', transform=lambda x: x.split('_', 2)[0], doc=
        """The event's namespace; every Shotgun event will have the domain ``"Shotgun"``.""")
    
    subtype = _item_property('event_type', transform=lambda x: x.split('_', 2)[2], doc=
        """The action associated with this event; Shotgun events are of the subtype:

        - ``"New"``: creation of an entity
        - ``"Change"``: updates to an entity
        - ``"Retirement"``: "deletion" of an entity
        - ``"Revival"``: "un-deletion" of an entity
        - ``"View"``: tracking that a human has viewed an entity

        """)

    user = _item_property('user', 
        """The ``HumanUser`` or ``ApiUser`` that triggered this event.""")

    meta = _item_property('meta')

    entity = _item_property('entity',
        """The entity, if availible.

        The entity will often not load immediately if it has been retired.
        :meth:`find_retired_entity` will attempt to find it.

        """)

    entity_type = _item_property('event_type', transform=lambda x: x.split('_')[1], doc="""
        The type of the entity.

        This is as reported by the event's :attr:`type`, which is always availible even
        if the entity is not. However, there is at least one case in which
        this differs from the type of the :attr:`entity`: ``"Reading"``.

        ``"Reading"`` appears to be a meta-type which is decribing when a human
        has read a note attached to an entity.

    """.strip())

    @property
    def entity_id(self):
        """The ID of the entity, which is sometimes availible even when the entity is not.

        There is an ``entity_id`` key in the :attr:`meta` dict, but there are
        circumstances in which that value is wrong. This property attempts to
        filter them out.

        """

        if self.entity:
            return self.entity['id']
        if 'entity_id' in self.meta:
            if self.subtype == 'Change' and 'actual_attribute_changed' in self.meta:
                # The metadata for backref changes is wrong; it refers to the
                # triggering entity, not the backref.
                return
            return self.meta['entity_id']

    @property
    def summary(self):

        parts = [self.type]

        if self.entity:
            parts.append('on %s:%d' % (self.entity['type'], self.entity['id']))
            if self.entity.get('name'):
                parts.append('("%s")' % self.entity['name'])
        else:
            parts.append('on %s:%s' % (self.entity_type, self.entity_id or 'unknown'))

        if self.user:
            parts.append('by %s:%d' % (self.user['type'], self.user['id']))
            if self.user.get('name'):
                parts.append('("%s")' % self.user['name'])

        return ' '.join(parts)


    def __str__(self):
        return '<Event %s>' % self.summary

    def dumps(self, pretty=False):
        return json.dumps(self, sort_keys=pretty, indent=4 if pretty else None, default=str)

    def find_retired_entity(self):
        """Find the "retired" entity that goes with this event log.

        If this event already has an entity, it will be returned. Ergo, this
        method can safely be called in all circumstances if you want an entity
        no matter where it comes from.

        .. warning:: This depends upon the ``$FROM$`` filter syntax,
            which is officially unsupported.

        """
        if not self.entity:
            e = self._shotgun.find_one(self.entity_type, [('$FROM$EventLogEntry.entity.id', 'is', self.id)])
            if not e:
                raise ValueError('could not find retired %s for event %d' % (self.entity_type, self.id))
            self['entity'] = e
        return self.entity
