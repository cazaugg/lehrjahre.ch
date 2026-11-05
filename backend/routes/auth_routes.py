from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import func, or_
from backend.models import db, User, email_domain
from backend.auth import (
    DUMMY_PASSWORD_HASH,
    verify_password,
    password_needs_rehash,
    hash_password,
    bump_session_version,
    ensure_csrf_token,
    get_current_user,
    login_required,
)
from backend.audit import audit
from backend.policies import serialize_user
from backend.ratelimit import login_email_limiter, login_ip_limiter
from backend.validation import parse_str

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = parse_str(data.get("email"), "E-Mail").lower()
    password = parse_str(data.get("password"), "Passwort", strip=False)

    if not email or not password:
        return jsonify({"error": "E-Mail und Passwort sind erforderlich."}), 400
    if (
        len(email) > 254
        or email_domain(email) is None
        or any(character.isspace() for character in email)
    ):
        return jsonify({"error": "Ungültige E-Mail-Adresse."}), 400

    ip_key = f"ip:{request.remote_addr or 'unknown'}"
    email_key = f"email:{email}"
    for limiter, key in (
        (login_ip_limiter, ip_key),
        (login_email_limiter, email_key),
    ):
        retry_after = limiter.retry_after(key)
        if retry_after is not None:
            audit("login_rate_limited", email=email)
            response = jsonify(
                {
                    "error": "Zu viele Anmeldeversuche. Bitte später erneut versuchen."
                }
            )
            response.status_code = 429
            response.headers["Retry-After"] = str(max(1, int(retry_after)))
            return response

    company_hint = parse_str(
        data.get("company_domain", data.get("company_email_domain")),
        "Firmendomain",
        default="",
        allow_none=True,
    )
    if company_hint:
        company_hint = company_hint.strip().lower().lstrip("@")

    matches = User.query.filter(
        or_(
            func.lower(User.company_email) == email,
            func.lower(User.private_email) == email,
            func.lower(User.school_email) == email,
        )
    ).all()
    if company_hint:
        from backend.models import Company

        matches = [
            candidate
            for candidate in matches
            if candidate.company_rel
            and (candidate.company_rel.email_domain or "").lower() == company_hint
        ]
    authenticated = [
        candidate
        for candidate in matches
        if verify_password(candidate.password_hash, password)
    ]

    if len(authenticated) != 1:
        if not matches:
            verify_password(DUMMY_PASSWORD_HASH, password)
        login_ip_limiter.hit(ip_key)
        login_email_limiter.hit(email_key)
        audit("login_failure", email=email)
        return jsonify({"error": "Ungültige Anmeldedaten."}), 401

    user = authenticated[0]
    login_email_limiter.reset(email_key)

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.session.commit()

    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["session_version"] = int(user.session_version or 0)
    csrf_token = ensure_csrf_token()
    audit("login_success", user_id=user.id)

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
    audit("logout")
    session.clear()
    return jsonify({"data": {"logged_out": True}})


@bp.route("/logout-all", methods=["POST"])
@login_required
def logout_all():
    user = get_current_user()
    bump_session_version(user)
    db.session.commit()
    audit("logout_all", user_id=user.id)
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
