from .tables import AuditLogMixin


class AppConfig:
    audit_log_class: AuditLogMixin


config = AppConfig()
