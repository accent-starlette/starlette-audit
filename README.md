<a href="https://travis-ci.org/accent-starlette/starlette-audit">
    <img src="https://travis-ci.org/accent-starlette/starlette-audit.svg?branch=master" alt="Build Status">
</a>

<a href="https://codecov.io/gh/accent-starlette/starlette-audit">
  <img src="https://codecov.io/gh/accent-starlette/starlette-audit/branch/master/graph/badge.svg" alt="Coverage" />
</a>

---

**Documentation**: [https://accent-starlette.github.io/](https://accent-starlette.github.io/)

---

# Starlette Audit Log

Usage:

```python
import sqlalchemy as sa
from starlette_audit.tables import Audited, AuditLogMixin
from starlette_auth.tables import User
from starlette_core.database import Base


class AuditLog(AuditLogMixin, Base):
    created_by_id = sa.Column(sa.Integer, sa.ForeignKey(User.id), nullable=True)
    created_by = sa.orm.relationship(User)

    __table_args__ = (
        sa.Index(
            "ix_auditlog_ctype",
            "entity_type",
            "entity_type_id",
        ),
    )


class BaseAudited(Audited):
    @classmethod
    def audit_class(cls):
        return AuditLog


class Parent(BaseAudited, Base):
    name = sa.Column(sa.String(), nullable=False, unique=True)

    def __str__(self):
        return self.name


class Child(BaseAudited, Base):
    name = sa.Column(sa.String(), nullable=False, unique=True)
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(Parent.id), nullable=True)
    age = sa.Column(sa.Integer, nullable=True)
    height = sa.Column(sa.Numeric(precision="0.00"), nullable=True)

    parent = sa.orm.relationship(Parent)

    def __str__(self):
        return self.name
```
