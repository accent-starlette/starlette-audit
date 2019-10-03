import sqlalchemy as sa
from sqlalchemy import orm
from starlette_auth.tables import User
from starlette_core.database import Base
from starlette_core.testing import assert_model_field

from starlette_audit import config
from starlette_audit.tables import Audited, AuditLogMixin


class AuditLog(AuditLogMixin, Base):
    created_by_id = sa.Column(sa.Integer, sa.ForeignKey(User.id), nullable=True)
    created_by = orm.relationship(User)

    __table_args__ = (sa.Index("ix_auditlog_ctype", "entity_type", "entity_type_id"),)


config.audit_log_class = AuditLog


class MyModel(Audited, Base):
    name = sa.Column(sa.String(50))


def test_fields():
    assert_model_field(AuditLog, "entity_type", sa.String, False, False, False, 255)
    assert_model_field(AuditLog, "entity_type_id", sa.String, False, False, False, 50)
    assert_model_field(AuditLog, "operation", sa.types.Enum, False, True, False)
    assert_model_field(AuditLog, "created_on", sa.DateTime, False, False, False)
    assert_model_field(AuditLog, "created_by_id", sa.Integer, True, False, False)
    assert_model_field(AuditLog, "data", sa.types.JSON, True, False, False)
    assert_model_field(AuditLog, "extra_data", sa.types.JSON, True, False, False)


def test_can_create(db, monkeypatch):
    db.create_all()

    user = User(email="foo@bar.com")
    user.save()

    def fake_request():
        return {"user": user}

    monkeypatch.setattr("starlette_audit.tables.get_request", fake_request)

    obj = MyModel(name="foo")
    obj.save()

    id = obj.id

    logs = AuditLog.query.filter(
        AuditLog.entity_type == "mymodel", AuditLog.entity_type_id == id
    ).all()

    assert len(logs) == 1
    assert logs[0].data == {"id": id, "name": "foo"}
    assert logs[0].extra_data == {}
    assert logs[0].operation == "INSERT"
    assert logs[0].created_by_id is user.id


def test_can_update(db, monkeypatch):
    db.create_all()

    user = User(email="foo@bar.com")
    user.save()

    def fake_request():
        return {"user": user}

    monkeypatch.setattr("starlette_audit.tables.get_request", fake_request)

    obj = MyModel(name="foo")
    obj.save()

    obj.name = "bar"
    obj.save()

    id = obj.id

    logs = AuditLog.query.filter(
        AuditLog.entity_type == "mymodel", AuditLog.entity_type_id == id
    ).all()

    assert len(logs) == 2
    assert logs[1].data == {"id": id, "name": "bar"}
    assert logs[1].extra_data == {}
    assert logs[1].operation == "UPDATE"
    assert logs[1].created_by_id == user.id


def test_can_delete(db, monkeypatch):
    db.create_all()

    user = User(email="foo@bar.com")
    user.save()

    def fake_request():
        return {"user": user}

    monkeypatch.setattr("starlette_audit.tables.get_request", fake_request)

    obj = MyModel(name="foo")
    obj.save()

    id = obj.id

    obj.delete()

    logs = AuditLog.query.filter(
        AuditLog.entity_type == "mymodel", AuditLog.entity_type_id == id
    ).all()

    # all logs should remain intact after deleting

    assert len(logs) == 2

    assert logs[0].data == {"id": id, "name": "foo"}
    assert logs[0].extra_data == {}
    assert logs[0].operation == "INSERT"
    assert logs[0].created_by_id == user.id

    assert logs[1].data == {"id": id, "name": "foo"}
    assert logs[1].extra_data == {}
    assert logs[1].operation == "DELETE"
    assert logs[1].created_by_id == user.id


def test_when_no_user(db):
    db.create_all()

    obj = MyModel(name="foo")
    obj.save()

    id = obj.id

    logs = AuditLog.query.filter(
        AuditLog.entity_type == "mymodel", AuditLog.entity_type_id == id
    ).all()

    assert len(logs) == 1
    assert logs[0].data == {"id": id, "name": "foo"}
    assert logs[0].extra_data == {}
    assert logs[0].operation == "INSERT"
    assert logs[0].created_by_id is None


def test_mapper_configuration(db):
    db.create_all()

    obj = MyModel(name="foo")
    obj.save()

    assert len(obj.auditlog) == 1
    assert isinstance(obj.auditlog[0], AuditLog)

    assert obj.auditlog[0].audited_instance == obj
