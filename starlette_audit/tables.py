import typing
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.sql.expression import cast
from starlette_core.middleware import get_request


class AuditLogMixin:
    """
    A mixin class that provides the basis for storing changes to model instances

    class AuditLog(AuditLogMixin, Base):
        created_by_id = sa.Column(sa.Integer, sa.ForeignKey(User.id), nullable=True)
        created_by = orm.relationship(User)

        __table_args__ = (
            sa.Index(
                "ix_auditlog_ctype",
                "entity_type",
                "entity_type_id",
            ),
        )

    """

    entity_type = sa.Column(sa.String(255), nullable=False)
    entity_type_id = sa.Column(sa.String(50), nullable=False)
    entity_name = sa.Column(sa.String(255), nullable=False)
    operation = sa.Column(sa.String(10), nullable=False, index=True)
    created_on = sa.Column(sa.DateTime, nullable=False, default=datetime.utcnow)
    data = sa.Column(sa.types.JSON)
    extra_data = sa.Column(sa.types.JSON)

    # placeholders to assign the user fields who created the entry
    created_by_id = None
    created_by = None

    @property
    def audited_instance(self):
        """ Instance the audit log item belongs too """

        return getattr(self, "audited_instance_%s" % self.entity_type)

    @property
    def data_keys(self):
        """ Returns a list of the keys in `self.data` """

        return sorted(self.data.keys())

    @property
    def extra_data_keys(self):
        """ Returns a list of the keys in `self.extra_data` """

        return sorted(self.extra_data.keys())

    @property
    def later_records(self):
        """ Returns all audit log entries after to this record """

        return self.__class__.query.filter(
            self.__class__.entity_type == self.entity_type,
            self.__class__.entity_type_id == self.entity_type_id,
            self.__class__.created_on > self.created_on,
        ).order_by(sa.desc(self.__class__.created_on))

    @property
    def prior_records(self):
        """ Returns all audit log entries prior to this record """

        return self.__class__.query.filter(
            self.__class__.entity_type == self.entity_type,
            self.__class__.entity_type_id == self.entity_type_id,
            self.__class__.created_on < self.created_on,
        ).order_by(sa.desc(self.__class__.created_on))


class Audited:
    """
    Mixin that activates the audit log for a model.
    Provides access to `instance.auditlog` and `.audited_instance` from an instance 
    of the audit log entry.

    class MyModel(Audited, Base):
        @classmethod
        def audit_class(cls):
            return MyAuditLog

    `Audited.manage_audit_manually` can be set to `True` to disable auto logging data
    to the audit log. This will enable you to add them yourself.

    `Audited.excluded_columns` can be set to a list of column
    names or relationship names you want to be excluded from collecting any data.
    """

    manage_audit_manually: bool = False
    excluded_columns: typing.List[str] = []

    @classmethod
    def audit_class(cls) -> "AuditLogMixin":
        """
        Should return the audit log class that will be used when tracking changes
        for your `Audited` model.
        """

        raise NotImplementedError("should return the audit log class")

    def audit_data(self):
        """ Returns a dict of data to store in the audit log """

        copied = self.__dict__.copy()
        data_dict = {}
        for key in self.__mapper__.columns.keys():
            #  exclude the field if required
            if key in self.excluded_columns:
                continue

            value = copied.get(key)

            # make the value json serializable
            if any(
                [
                    isinstance(value, Decimal),
                    isinstance(value, datetime),
                    isinstance(value, date),
                    isinstance(value, UUID),
                ]
            ):
                value = str(value)
            elif isinstance(value, Enum):
                value = value.name

            data_dict[key] = value

        return data_dict

    def audit_extra_data(self):
        """
        Returns extra data to store in the audit log such as the string value
        of a relationship.

        Possible uses could be to add arbitrary messages to the dict.
        """

        data_dict = {}
        copied = self.__dict__.copy()
        related = self.__mapper__.relationships.keys()

        for field in related:
            try:
                #  exclude the field if required
                if field in self.excluded_columns:
                    continue

                value = copied.get(field) or getattr(self, field)

                # dont store the value if its a list of entities
                # or its None
                if value is None:
                    continue
                elif isinstance(value, list):
                    continue

                data_dict[field] = str(value)
            except:
                continue

        return data_dict


@sa.event.listens_for(Audited, "mapper_configured", propagate=True)
def setup_listener(mapper, class_):
    """
    Creates the mapping between an instance of a model that inherits from 'Audited'
    and the 'AuditLog' itself.
    Provides access to `instance.auditlog` and `.audited_instance` from an instance 
    of the audit log entry.
    """

    audit_log_class = class_.audit_class()

    assert issubclass(
        audit_log_class, AuditLogMixin
    ), f"{class_}.audit_class should return a subclass of 'AuditLogMixin'"

    class_.auditlog = orm.relationship(
        audit_log_class,
        primaryjoin=sa.and_(
            cast(class_.id, sa.String)
            == orm.foreign(orm.remote(audit_log_class.entity_type_id)),
            audit_log_class.entity_type == class_.__table__.name,
        ),
        backref=orm.backref(
            "audited_instance_%s" % class_.__table__.name,
            primaryjoin=orm.remote(cast(class_.id, sa.String))
            == orm.foreign(audit_log_class.entity_type_id),
        ),
        order_by=sa.desc(audit_log_class.created_on),
        passive_deletes=True,
    )


def add_auditlog_entry(mapper, connection, target, operation):
    request = get_request()
    user_id = None
    if request and "user" in request:
        user_id = getattr(request["user"], "id")

    # ensure entity name is no longer than 255 chars
    target_str = str(target)
    entity_name = (target_str[:253] + "..") if len(target_str) > 253 else target_str

    connection.execute(
        mapper.relationships["auditlog"]
        .target.insert()
        .values(
            {
                "entity_type": mapper.class_.__table__.name,
                "entity_type_id": target.id,
                "entity_name": entity_name,
                "operation": operation,
                "created_by_id": user_id,
                "data": target.audit_data(),
                "extra_data": target.audit_extra_data(),
            }
        )
    )


@sa.event.listens_for(Audited, "after_insert", propagate=True)
def receive_after_insert(mapper, connection, target):
    if not mapper.class_.manage_audit_manually:
        add_auditlog_entry(mapper, connection, target, "INSERT")


@sa.event.listens_for(Audited, "after_update", propagate=True)
def receive_after_update(mapper, connection, target):
    if not mapper.class_.manage_audit_manually:
        add_auditlog_entry(mapper, connection, target, "UPDATE")


@sa.event.listens_for(Audited, "after_delete", propagate=True)
def receive_after_delete(mapper, connection, target):
    if not mapper.class_.manage_audit_manually:
        add_auditlog_entry(mapper, connection, target, "DELETE")
