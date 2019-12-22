import sqlalchemy as sa
from sqlalchemy import orm
from starlette.authentication import has_required_scope
from starlette.routing import Route, Router
from starlette_admin import config
from starlette_admin.admin import BaseAdmin, ModelAdmin
from starlette_core.database import Base


class AuditedModelAdmin(ModelAdmin):
    list_template: str = "starlette_audit/list.html"
    update_template: str = "starlette_audit/update.html"
    audit_log_item_list_template: str = "starlette_audit/item_audit_list.html"
    audit_log_item_template: str = "starlette_audit/item_audit.html"
    audit_log_deleted_template: str = "starlette_audit/deleted_entries.html"

    @classmethod
    def audit_log_class(cls):
        return cls.model_class.audit_class()

    @classmethod
    async def audit_log_deleted_view(cls, request):
        if not has_required_scope(request, cls.permission_scopes):
            raise HTTPException(403)

        list_objects = (
            cls.audit_log_class()
            .query.filter_by(
                entity_type=cls.model_class.__table__.name, operation="DELETE"
            )
            .all()
        )
        context = cls.get_context(request)
        context.update({"list_objects": list_objects})

        return config.templates.TemplateResponse(
            cls.audit_log_deleted_template, context
        )

    @classmethod
    async def audit_log_view(cls, request):
        if not has_required_scope(request, cls.permission_scopes):
            raise HTTPException(403)

        instance = cls.get_object(request)
        instance.auditlog
        context = cls.get_context(request)
        context.update({"object": instance})

        return config.templates.TemplateResponse(
            cls.audit_log_item_list_template, context
        )

    @classmethod
    async def audit_log_item_view(cls, request):
        if not has_required_scope(request, cls.permission_scopes):
            raise HTTPException(403)

        instance = cls.get_object(request)

        item_id = request.path_params["item_id"]
        item = cls.audit_log_class().query.get_or_404(item_id)

        items = item.data_keys
        extra_items = item.extra_data_keys

        diff = None
        diff_id = request.path_params.get("diff_id")
        if diff_id:
            diff = cls.audit_log_class().query.get_or_404(diff_id)
            items = sorted(list(set(items + diff.data_keys)))
            extra_items = sorted(list(set(extra_items + diff.extra_data_keys)))

        context = cls.get_context(request)
        context.update(
            {
                "object": instance,
                "item": item,
                "diff": diff,
                "items": items,
                "extra_items": extra_items,
            }
        )

        return config.templates.TemplateResponse(cls.audit_log_item_template, context)

    @classmethod
    def url_names(cls):
        url_names = super().url_names()
        mount = cls.mount_name()
        url_names["audit"] = f"{cls.site.name}:{mount}_audit"
        url_names["audit_deleted"] = f"{cls.site.name}:{mount}_audit_deleted"
        url_names["audit_item"] = f"{cls.site.name}:{mount}_audit_item"
        url_names["audit_item_diff"] = f"{cls.site.name}:{mount}_audit_item_diff"
        return url_names

    @classmethod
    def routes(cls):
        routes = super().routes()
        mount = cls.mount_name()
        routes.add_route(
            path=f"/{cls.routing_id_part}/audit",
            endpoint=cls.audit_log_view,
            methods=["GET"],
            name=f"{mount}_audit",
        )
        routes.add_route(
            path="/audit/deleted",
            endpoint=cls.audit_log_deleted_view,
            methods=["GET"],
            name=f"{mount}_audit_deleted",
        )
        routes.add_route(
            path=f"/{cls.routing_id_part}/audit/{{item_id}}",
            endpoint=cls.audit_log_item_view,
            methods=["GET"],
            name=f"{mount}_audit_item",
        )
        routes.add_route(
            path=f"/{cls.routing_id_part}/audit/{{item_id}}/diff/{{diff_id}}",
            endpoint=cls.audit_log_item_view,
            methods=["GET"],
            name=f"{mount}_audit_item_diff",
        )
        return routes


class AuditLogAdmin(BaseAdmin):
    audit_log_class: Base
    audit_log_limit_records: int = 100
    search_enabled: bool = True
    list_template: str = "starlette_audit/audit_log_list.html"
    item_template: str = "starlette_audit/audit_log_item.html"

    @classmethod
    def get_context(cls, request):
        context = super().get_context(request)
        context.update({"limit": cls.audit_log_limit_records})
        return context

    @classmethod
    def get_list_objects(cls, request):
        qs = cls.audit_log_class.query
        qs = qs.options(orm.contains_eager("created_by"))
        qs = qs.outerjoin("created_by")
        search = request.query_params.get("search", "").strip().lower()
        if search:
            qs = cls.get_search_results(qs, search)
        return (
            qs.order_by(sa.desc(cls.audit_log_class.created_on))
            .limit(cls.audit_log_limit_records)
            .all()
        )

    @classmethod
    def get_search_results(cls, qs: orm.Query, term: str) -> orm.Query:
        user_cls = cls.audit_log_class.__mapper__.relationships["created_by"].argument
        for t in term.split(" "):
            search = f"%{t}%"
            qs = qs.filter(
                sa.or_(
                    cls.audit_log_class.operation.ilike(search),
                    cls.audit_log_class.entity_type.ilike(search),
                    cls.audit_log_class.entity_name.ilike(search),
                    user_cls.first_name.ilike(search),
                    user_cls.last_name.ilike(search),
                )
            )
        return qs

    @classmethod
    async def audit_log_item_view(cls, request):
        if not has_required_scope(request, cls.permission_scopes):
            raise HTTPException(403)

        item_id = request.path_params["item_id"]
        item = cls.audit_log_class().query.get_or_404(item_id)

        items = item.data_keys
        extra_items = item.extra_data_keys

        diff = None
        diff_id = request.path_params.get("diff_id")
        if diff_id:
            diff = cls.audit_log_class().query.get_or_404(diff_id)
            items = sorted(list(set(items + diff.data_keys)))
            extra_items = sorted(list(set(extra_items + diff.extra_data_keys)))

        context = cls.get_context(request)
        context.update(
            {"item": item, "diff": diff, "items": items, "extra_items": extra_items}
        )

        return config.templates.TemplateResponse(cls.item_template, context)

    @classmethod
    def url_names(cls):
        mount = cls.mount_name()
        return {
            "list": f"{cls.site.name}:{mount}_list",
            "audit_item": f"{cls.site.name}:{mount}_audit_item",
            "audit_item_diff": f"{cls.site.name}:{mount}_audit_item_diff",
        }

    @classmethod
    def routes(cls):
        mount = cls.mount_name()
        return Router(
            [
                Route(
                    "/", endpoint=cls.list_view, methods=["GET"], name=f"{mount}_list"
                ),
                Route(
                    "/{item_id}",
                    endpoint=cls.audit_log_item_view,
                    methods=["GET"],
                    name=f"{mount}_audit_item",
                ),
                Route(
                    "/{item_id}/diff/{diff_id}",
                    endpoint=cls.audit_log_item_view,
                    methods=["GET"],
                    name=f"{mount}_audit_item_diff",
                ),
            ]
        )
