from starlette.authentication import has_required_scope
from starlette_admin import config
from starlette_admin.admin import ModelAdmin


class AuditedModelAdmin(ModelAdmin):
    list_template: str = "starlette_audit/list.html"
    update_template: str = "starlette_audit/update.html"
    audit_log_item_list_template: str = "starlette_audit/item_audit_list.html"
    audit_log_item_template: str = "starlette_audit/item_audit.html"
    audit_log_deleted_template: str = "starlette_audit/deleted_entries.html"

    @classmethod
    async def audit_log_deleted_view(cls, request):
        if not has_required_scope(request, cls.permission_scopes):
            raise HTTPException(403)

        from starlette_audit import config as audit_config

        list_objects = audit_config.audit_log_class.query.filter_by(
            entity_type=cls.model_class.__table__.name, operation="DELETE"
        ).all()
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

        from starlette_audit import config as audit_config

        item_id = request.path_params["item_id"]
        item = audit_config.audit_log_class.query.get_or_404(item_id)

        items = item.data_keys
        extra_items = item.extra_data_keys

        diff = None
        diff_id = request.path_params.get("diff_id")
        if diff_id:
            diff = audit_config.audit_log_class.query.get_or_404(diff_id)
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
            path="/{id:int}/audit",
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
            path="/{id:int}/audit/{item_id:int}",
            endpoint=cls.audit_log_item_view,
            methods=["GET"],
            name=f"{mount}_audit_item",
        )
        routes.add_route(
            path="/{id:int}/audit/{item_id:int}/diff/{diff_id:int}",
            endpoint=cls.audit_log_item_view,
            methods=["GET"],
            name=f"{mount}_audit_item_diff",
        )
        return routes
