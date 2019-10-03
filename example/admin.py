import sqlalchemy as sa
from sqlalchemy import orm
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse
from starlette.routing import Route, Router
from starlette_admin.admin import ModelAdmin
from starlette_audit.admin import AuditedModelAdmin
from wtforms import fields, form, validators
from wtforms_alchemy import ModelForm
from wtforms_alchemy.fields import QuerySelectField

from .models import Child, Parent


# objects using the model admin
####################################################################


class ParentForm(ModelForm):
    class Meta:
        model = Parent

    @classmethod
    def get_session(cls):
        from starlette_core.database import Session
        return Session()


class ParentAdmin(ModelAdmin):
    section_name = "People"
    collection_name = "Parents"
    model_class = Parent
    list_field_names = ["name"]
    paginate_by = 10
    order_enabled = True
    search_enabled = True
    create_form = ParentForm
    update_form = ParentForm
    delete_form = form.Form


def parents():
    return Parent.query.order_by("name")


class ChildForm(ModelForm):
    name = fields.StringField(validators=[validators.DataRequired()])
    age = fields.IntegerField(validators=[validators.Optional()])
    height = fields.DecimalField(places=2, validators=[validators.Optional()])
    parent = QuerySelectField(
        query_factory=parents, allow_blank=True, blank_text="Please select..."
    )

    class Meta:
        model = Child

    @classmethod
    def get_session(cls):
        from starlette_core.database import Session
        return Session()


class ChildAdmin(AuditedModelAdmin):
    section_name = "People"
    collection_name = "Children"
    model_class = Child
    list_field_names = ["name", "description"]
    paginate_by = 10
    order_enabled = True
    search_enabled = True
    create_form = ChildForm
    update_form = ChildForm
    delete_form = form.Form

    @classmethod
    def get_default_ordering(cls, qs: orm.Query) -> orm.Query:
        return qs.order_by("name")

    @classmethod
    def get_search_results(cls, qs: orm.Query, term: str) -> orm.Query:
        return qs.filter(
            sa.or_(
                Child.name.like(f"%{term}%"),
                Child.description.like(f"%{term}%")
            )
        )
