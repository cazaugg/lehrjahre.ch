import logging
import os
import secrets
from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from backend.config import Config, DATA_DIR, INSECURE_DEFAULT_SECRET
from backend.models import db
from backend import tenants
from backend.auth import verify_csrf
from backend.validation import ValidationError
from backend.routes.auth_routes import bp as auth_bp
from backend.routes.user_routes import bp as user_bp
from backend.routes.project_routes import bp as project_bp
from backend.routes.implementation_routes import bp as implementation_bp
from backend.routes.evaluation_routes import bp as evaluation_bp
from backend.routes.documents_routes import bp as documents_bp
from backend.routes.grades_routes import bp as grades_bp
from backend.routes.knowledge_routes import bp as knowledge_bp
from backend.routes.lehrplan_routes import bp as lehrplan_bp


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    is_dev = bool(app.config.get("IS_DEV"))
    secret_key = app.config.get("SECRET_KEY")
    if not secret_key:
        if is_dev:
            app.config["SECRET_KEY"] = secrets.token_hex(32)
            app.logger.warning(
                "SECRET_KEY is not set; using an ephemeral development key."
            )
        else:
            raise RuntimeError(
                "SECRET_KEY must be set when LEHRJAHRE_ENV is not development."
            )
    elif not is_dev and secret_key == INSECURE_DEFAULT_SECRET:
        raise RuntimeError(
            "The development SECRET_KEY must not be used in production."
        )
    elif not is_dev and len(str(secret_key)) < 32:
        raise RuntimeError(
            "SECRET_KEY must be at least 32 characters outside development."
        )
    if app.config.get("DEBUG") and not is_dev:
        raise RuntimeError(
            "Debug mode is only allowed when LEHRJAHRE_ENV=development."
        )

    # Reverse proxy / WAF support (X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Audit entries are written at INFO level; do not let the default root
    # logger filter them out in production.
    app.logger.setLevel(logging.INFO)

    os.makedirs(DATA_DIR, mode=0o750, exist_ok=True)
    os.makedirs(app.config["COMPANY_ROOT"], mode=0o750, exist_ok=True)
    for directory in (DATA_DIR, app.config["COMPANY_ROOT"]):
        try:
            os.chmod(directory, 0o750)
        except OSError:
            pass

    db.init_app(app)

    # The tenant context is set per request by auth.get_current_user; clear
    # any leftover context before (and after) every request so a reused
    # thread can never operate on the wrong company database.
    @app.before_request
    def clear_tenant_context():
        tenants.clear_tenant_company()

    @app.teardown_request
    def cleanup_tenant_context(_error):
        tenants.clear_tenant_company()

    @app.before_request
    def check_csrf():
        if request.path.startswith("/api/"):
            res = verify_csrf()
            if res is not None:
                return res

    @app.before_request
    def validate_json_object():
        if (
            request.path.startswith("/api/")
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.is_json
        ):
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"error": "Ungültiger JSON-Body."}), 400

    # Register API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(implementation_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(grades_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(lehrplan_bp)

    @app.errorhandler(ValidationError)
    def invalid_request(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({"error": "Die hochgeladene Datei ist zu gross (Max. 20 MB)."}), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled API error")
        return jsonify({"error": "Interner Serverfehler."}), 500

    @app.route("/api/health")
    def api_health():
        return jsonify({"service": "lehrjahre.ch API", "status": "ok"})

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Endpunkt nicht gefunden."}), 404
        return jsonify({"error": "Nicht gefunden."}), 404

    with app.app_context():
        # Create the control schema (company registry + user routing index).
        # Company databases are provisioned on demand by tenants.create_company_schema.
        from backend.models import Company, UserRouting

        db.metadata.create_all(
            bind=db.engine, tables=[Company.__table__, UserRouting.__table__]
        )

        database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if database_uri.startswith("sqlite:///"):
            database_path = database_uri[len("sqlite:///") :]
            try:
                os.chmod(database_path, 0o640)
            except OSError:
                pass

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("LEHRJAHRE_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=bool(app.config["DEBUG"]))
