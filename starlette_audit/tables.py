from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import orm
from starlette_core.middleware import get_request

from .encoder import prepare_data

operation_enum = sa.types.Enum("INSERT", "DELETE", "UPDATE", name="operation")


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
    operation = sa.Column(operation_enum, nullable=False, index=True)
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
    def history(self):
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
    """

    @classmethod
    def audit_class(cls) -> "AuditLogMixin":
        """
        Should return the audit log class that will be used when tracking changes
        for your `Audited` model.
        """

        raise NotImplementedError("should return the audit log class")


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
            class_.id == orm.foreign(orm.remote(audit_log_class.entity_type_id)),
            audit_log_class.entity_type == class_.__table__.name,
        ),
        backref=orm.backref(
            "audited_instance_%s" % class_.__table__.name,
            primaryjoin=orm.remote(class_.id)
            == orm.foreign(audit_log_class.entity_type_id),
        ),
        order_by=sa.desc(audit_log_class.created_on),
        passive_deletes=True,
    )


def add_auditlog_entry(mapper, connection, target, operation):
    audit_log_table = mapper.relationships["auditlog"].target

    copied = target.__dict__.copy()
    data_dict = dict([(key, copied.get(key)) for key in mapper.columns.keys()])
    data = prepare_data(data_dict)

    extra_data = dict(
        [
            (key, str(copied.get(key)))
            for key in mapper.relationships.keys()
            if key != "auditlog" and copied.get(key)
        ]
    )
    request = get_request()

    user_id = None
    if request and "user" in request:
        user_id = getattr(request["user"], "id")

    connection.execute(
        audit_log_table.insert().values(
            {
                "entity_type": target.__class__.__table__.name,
                "entity_type_id": target.id,
                "entity_name": str(target),
                "operation": operation,
                "created_by_id": user_id,
                "data": data,
                "extra_data": extra_data,
            }
        )
    )


@sa.event.listens_for(Audited, "after_insert", propagate=True)
def receive_after_insert(mapper, connection, target):
    add_auditlog_entry(mapper, connection, target, "INSERT")


@sa.event.listens_for(Audited, "after_update", propagate=True)
def receive_after_update(mapper, connection, target):
    add_auditlog_entry(mapper, connection, target, "UPDATE")


@sa.event.listens_for(Audited, "after_delete", propagate=True)
def receive_after_delete(mapper, connection, target):
    add_auditlog_entry(mapper, connection, target, "DELETE")
