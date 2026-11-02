import os
from flask import Flask, send_from_directory, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from backend.config import Config, DATA_DIR, DOCUMENTS_DIR
from backend.models import db
from backend.auth import verify_csrf
from backend.routes.auth_routes import bp as auth_bp
from backend.routes.user_routes import bp as user_bp
from backend.routes.project_routes import bp as project_bp
from backend.routes.implementation_routes import bp as implementation_bp
from backend.routes.evaluation_routes import bp as evaluation_bp
from backend.routes.documents_routes import bp as documents_bp
from backend.routes.grades_routes import bp as grades_bp
from backend.routes.knowledge_routes import bp as knowledge_bp


def create_app(config_overrides: dict | None = None) -> Flask:
    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    )
    app = Flask(__name__, static_folder=frontend_dist, static_url_path="")
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    # Reverse proxy / WAF support (X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(app.config["DOCUMENTS_ROOT"], exist_ok=True)

    db.init_app(app)

    @app.before_request
    def check_csrf():
        if request.path.startswith("/api/"):
            res = verify_csrf()
            if res is not None:
                return res

    # Register API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(implementation_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(grades_bp)
    app.register_blueprint(knowledge_bp)

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({"error": "Die hochgeladene Datei ist zu gross (Max. 20 MB)."}), 413

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path.startswith("api/"):
            return jsonify({"error": "Endpunkt nicht gefunden."}), 404
        if os.path.isdir(frontend_dist):
            full_path = os.path.join(frontend_dist, path)
            if path and os.path.isfile(full_path):
                return send_from_directory(frontend_dist, path)
            index_file = os.path.join(frontend_dist, "index.html")
            if os.path.isfile(index_file):
                return send_from_directory(frontend_dist, "index.html")
        return jsonify(
            {
                "service": "lehrjahre.ch API",
                "status": "ok",
            }
        )

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
