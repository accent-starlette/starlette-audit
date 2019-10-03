from starlette_audit import config, tables
import sqlalchemy as sa
from starlette_auth.tables import User
from starlette_core.database import Base


class AuditLog(tables.AuditLogMixin, Base):
    created_by_id = sa.Column(sa.Integer, sa.ForeignKey(User.id), nullable=True)
    created_by = sa.orm.relationship(User)

    __table_args__ = (
        sa.Index(
            "ix_auditlog_ctype",
            "entity_type",
            "entity_type_id",
        ),
    )


config.audit_log_class = AuditLog


class Parent(Base):
    name = sa.Column(sa.String(), nullable=False, unique=True)

    def __str__(self):
        return self.name


class Child(tables.Audited, Base):
    name = sa.Column(sa.String(), nullable=False, unique=True)
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(Parent.id), nullable=True)
    age = sa.Column(sa.Integer, nullable=True)
    height = sa.Column(sa.Numeric(precision="0.00"), nullable=True)

    parent = sa.orm.relationship(Parent)

    def __str__(self):
        return self.name
