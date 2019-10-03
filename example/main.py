import jinja2
import starlette_admin
import starlette_auth
from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, AuthenticationBackend, SimpleUser
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette_admin.config import config
from starlette_admin.site import AdminSite
from starlette_core.database import Database, DatabaseURL
from starlette_core.middleware import DatabaseMiddleware
from starlette_core.templating import Jinja2Templates

from .admin import ChildAdmin, ParentAdmin

DEBUG = True

templates = Jinja2Templates(
    loader=jinja2.ChoiceLoader(
        [
            jinja2.PackageLoader("starlette_admin", "templates"),
            jinja2.PackageLoader("starlette_audit", "templates"),
        ]
    )
)

# config
starlette_admin.config.logout_url = '/auth/logout'
starlette_admin.config.templates = templates
starlette_auth.config.change_pw_template = "starlette_admin/auth/change_password.html"
starlette_auth.config.login_template = "starlette_admin/auth/login.html"
starlette_auth.config.templates = templates

url = DatabaseURL("sqlite:///example/db.sqlite3")

db = Database(url)
db.create_all()

# create an admin site
adminsite = AdminSite(name="admin", permission_scopes=[])
# register admins
adminsite.register(ChildAdmin)
adminsite.register(ParentAdmin)

# create app
app = Starlette(debug=DEBUG)

app.mount(
    path="/static",
    app=StaticFiles(directory="static", packages=["starlette_admin"]),
    name="static"
)

app.add_middleware(AuthenticationMiddleware, backend=starlette_auth.ModelAuthBackend())
app.add_middleware(SessionMiddleware, secret_key="secret")
app.add_middleware(DatabaseMiddleware)

# mount admin site
app.mount(path="/", app=adminsite, name=adminsite.name)
app.mount(path="/auth", app=starlette_auth.app, name="auth")
