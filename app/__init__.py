from flask import Flask

from app.routes.access_routes import access_bp
from app.routes.auth_routes import auth_bp
from app.routes.firewall_routes import firewall_bp
from app.routes.nginx_routes import nginx_bp
from app.routes.system_routes import system_bp
from app.routes.subscription_routes import subscription_bp
from app.routes.webhook_routes import webhook_bp
from app.routes.user_routes import users_bp
from app.routes.web_routes import web_bp
from app.routes.xray_routes import xray_bp
from app.services.db_service import init_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    init_db()

    app.register_blueprint(web_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(access_bp, url_prefix="/api/access")
    app.register_blueprint(system_bp, url_prefix="/api/system")
    app.register_blueprint(firewall_bp, url_prefix="/api/firewall")
    app.register_blueprint(nginx_bp, url_prefix="/api/nginx")
    app.register_blueprint(xray_bp, url_prefix="/api/xray")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(subscription_bp, url_prefix="/api/subscription")
    app.register_blueprint(webhook_bp, url_prefix="/api/webhook")
    return app
