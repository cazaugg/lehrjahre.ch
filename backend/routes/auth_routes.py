from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import or_
from backend.models import User
from backend.auth import (
    verify_password,
    ensure_csrf_token,
    get_current_user,
    login_required,
)
from backend.policies import serialize_user

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "E-Mail und Passwort sind erforderlich."}), 400

    user = User.query.filter(
        or_(
            User.company_email.ilike(email),
            User.private_email.ilike(email),
            User.school_email.ilike(email),
        )
    ).first()

    if not user or not verify_password(user.password_hash, password):
        return jsonify({"error": "Ungültige Anmeldedaten."}), 401

    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    csrf_token = ensure_csrf_token()

    return jsonify(
        {
            "data": {
                "user": serialize_user(user, user),
                "csrf_token": csrf_token,
                "mem_professions": current_app.config["MEM_PROFESSIONS"],
                "trainer_functions": current_app.config["TRAINER_FUNCTIONS"],
            }
        }
    )


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return jsonify({"data": {"logged_out": True}})


@bp.route("/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user:
        return jsonify({"data": {"user": None, "csrf_token": ensure_csrf_token()}})

    return jsonify(
        {
            "data": {
                "user": serialize_user(user, user),
                "csrf_token": ensure_csrf_token(),
                "mem_professions": current_app.config["MEM_PROFESSIONS"],
                "trainer_functions": current_app.config["TRAINER_FUNCTIONS"],
            }
        }
    )
