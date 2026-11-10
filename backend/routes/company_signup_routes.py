"""Self-service company signup.

Flow:

1. ``POST /api/company-signup`` stores a *pending* signup in the control
   database (no company is created yet) and mails a one-time verification
   link from ``kontakt@lehrjahre.ch``. The signup e-mail's domain becomes
   the claimed company ``email_domain`` — controlling that mailbox is the
   domain proof — so public/free mail providers are rejected upfront.
2. ``POST /api/company-signup/resend`` delivers a fresh link (previous
   links become invalid because only the latest token hash is stored).
3. ``POST /api/company-signup/verify`` consumes the one-time token and
   provisions the tenant (registry row + folder + ``app.db``), creates the
   admin account inside it and logs the person in.

Security properties: the token is 256-bit, stored hashed (SHA-256,
single-use, time-limited); the endpoints are unauthenticated
(CSRF-exempt like login, see ``auth.verify_csrf``) but rate limited;
submit and resend answers are generic so they cannot confirm or deny
foreign e-mail addresses.
"""

import hashlib
import shutil
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import func, or_

from backend import tenants
from backend.audit import audit
from backend.auth import hash_password, ensure_csrf_token
from backend.mail import MailDeliveryError, send_registration_verification
from backend.models import (
    company_signup_apply_token,
    db,
    Company,
    CompanySignup,
    User,
    UserRouting,
    email_domain,
    is_public_email_domain,
    normalize_email_domain,
)
from backend.policies import serialize_user
from backend.routes.user_routes import sync_user_routing
from backend.ratelimit import (
    signup_ip_limiter,
    signup_resend_ip_limiter,
    signup_resend_limiter,
    verify_ip_limiter,
    verify_token_limiter,
)
from backend.storage import slugify_company
from backend.validation import parse_str

bp = Blueprint("api_company_signup", __name__, url_prefix="/api/company-signup")

MAX_PASSWORD_LEN = 512


def _utcnow():
    """SQLite drops timezones on DateTime round-trips; use naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProvisionError(RuntimeError):
    """Tenant provisioning failed; partial state was already cleaned up."""


def _enabled_or_403():
    if not current_app.config.get("SIGNUP_ENABLED", True):
        return jsonify(
            {"error": "Die Registrierung ist derzeit deaktiviert."}
        ), 403
    return None


def _generic_response():
    """Answer used whenever nothing sensitive may be revealed."""
    return jsonify(
        {
            "data": {
                "message": (
                    "Falls die Registrierung möglich ist, senden wir Ihnen "
                    "jetzt eine E-Mail. Bitte prüfen Sie Ihr Postfach."
                )
            }
        }
    )


def _rate_limited(limiter, key):
    retry_after = limiter.retry_after(key)
    if retry_after is not None:
        response = jsonify(
            {"error": "Zu viele Anfragen. Bitte später erneut versuchen."}
        )
        response.status_code = 429
        response.headers["Retry-After"] = str(max(1, int(retry_after)))
        return response
    return None


def _validate_submit(data):
    """Validate the submitted form. Returns (error_response_or_None, values).

    An error_response is a `(jsonify_response, 400)` tuple ready to return.
    """
    name = parse_str(data.get("name"), "Vorname")
    surname = parse_str(data.get("surname"), "Nachname")
    raw_email = parse_str(data.get("email"), "E-Mail").lower()
    job_title = parse_str(data.get("job_title"), "Beruf/Funktion")
    company_name = parse_str(data.get("company_name"), "Firmenname")
    address = parse_str(data.get("address"), "Firmenadresse", allow_none=True)
    password = parse_str(
        data.get("password"), "Passwort", default="", strip=False
    )

    if not name or not surname or not raw_email or not job_title or not company_name:
        return (
            jsonify(
                {
                    "error": (
                        "Vorname, Nachname, Firmen-E-Mail, Beruf/Funktion "
                        "und Firmenname sind Pflichtfelder."
                    )
                }
            ),
            400,
        ), None
    if len(name) > 120 or len(surname) > 120:
        return (jsonify({"error": "Vor- und Nachname sind zu lang."}), 400), None
    if len(company_name) > 150:
        return (jsonify({"error": "Der Firmenname ist zu lang."}), 400), None
    if len(job_title) > 150:
        return (jsonify({"error": "Die Angabe Beruf/Funktion ist zu lang."}), 400), None
    if address and len(address) > 255:
        return (jsonify({"error": "Die Firmenadresse ist zu lang."}), 400), None

    if (
        len(raw_email) > 254
        or email_domain(raw_email) is None
        or any(character.isspace() for character in raw_email)
    ):
        return (jsonify({"error": "Ungültige E-Mail-Adresse."}), 400), None

    domain = email_domain(raw_email)
    if is_public_email_domain(domain):
        return (
            jsonify(
                {
                    "error": (
                        "Bitte melden Sie sich mit Ihrer Firmen-E-Mail an: "
                        f"@{domain} kann nicht als Firmen-Domain verwendet werden."
                    )
                }
            ),
            400,
        ), None

    if not password:
        return (jsonify({"error": "Passwort ist erforderlich."}), 400), None
    if len(password) < 8:
        return (
            jsonify(
                {"error": "Das Passwort muss mindestens 8 Zeichen lang sein."}
            ),
            400,
        ), None
    if len(password) > MAX_PASSWORD_LEN:
        return (jsonify({"error": "Das Passwort ist zu lang."}), 400), None
    if "\x00" in password:
        return (
            jsonify({"error": "Das Passwort enthält ungültige Zeichen."}),
            400,
        ), None

    values = {
        "name": name,
        "surname": surname,
        "email": raw_email,
        "domain": domain,
        "job_title": job_title,
        "company_name": company_name,
        "address": address or "",
        # The plaintext password never leaves this scope.
        "password_hash": hash_password(password),
    }
    return None, values


def _name_conflict_response(values):
    """Honest error answers for company-name collisions. These reveal
    nothing sensitive (the same is stated on the login page hint)."""
    lowered = values["company_name"].strip().lower()
    target_slug = slugify_company(values["company_name"])
    for existing in Company.query.all():
        if (existing.name or "").strip().lower() == lowered:
            return jsonify(
                {"error": f"Firma '{values['company_name']}' existiert bereits."}
            ), 400
        if slugify_company(existing.name) == target_slug:
            return jsonify(
                {
                    "error": (
                        f"Der Firmenname '{values['company_name']}' kollidiert "
                        f"mit dem Ordner von '{existing.name}'."
                    )
                }
            ), 400
    return None


@bp.route("/domain-check", methods=["GET"])
def domain_check():
    """Availability hint for the signup form (derived from the e-mail)."""
    domain = (request.args.get("domain") or "").strip().lower().lstrip("@")
    try:
        domain = normalize_email_domain(domain)
    except ValueError:
        return jsonify({"data": {"valid": False, "available": False}})
    available = not is_public_email_domain(domain) and (
        Company.query.filter_by(email_domain=domain).first() is None
    )
    return jsonify(
        {"data": {"valid": True, "available": available, "domain": domain}}
    )


def _active_pending_signup(email: str):
    """Latest pending signup for an (lowercased) address, else None."""
    if not email or email_domain(email) is None:
        return None
    return (
        CompanySignup.query.filter(
            func.lower(CompanySignup.email) == email,
            CompanySignup.status == CompanySignup.STATUS_PENDING,
        )
        .order_by(CompanySignup.id.desc())
        .first()
    )


def _send_verification(signup, token: str, resend: bool):
    """Mail the verification link for `token`. Error response or None."""
    signup.resend_count = (signup.resend_count or 0) + (1 if resend else 0)
    signup.last_sent_at = _utcnow()

    base_url = current_app.config.get("LEHRJAHRE_PUBLIC_URL") or ""
    verify_url = f"{base_url}/registrierung/bestaetigen?token={token}"
    full_name = f"{signup.name} {signup.surname}".strip()
    try:
        send_registration_verification(signup.email, full_name, verify_url)
    except MailDeliveryError:
        audit("company_signup_mail_failed", resend=resend)
        db.session.commit()  # keep the pending signup (token can be re-issued)
        return jsonify(
            {
                "error": (
                    "Die Bestätigungs-E-Mail konnte gerade nicht gesendet "
                    "werden. Bitte versuchen Sie es später erneut."
                )
            }
        ), 502
    db.session.commit()
    audit("company_signup_requested", resend=resend, domain=signup.email_domain)
    return None


@bp.route("", methods=["POST"])
def submit():
    guard = _enabled_or_403()
    if guard is not None:
        return guard

    data = request.get_json(silent=True) or {}
    ip_key = f"ip:{request.remote_addr or 'unknown'}"
    limited = _rate_limited(signup_ip_limiter, ip_key)
    if limited is not None:
        return limited

    error, values = _validate_submit(data)
    if error is not None:
        return error

    signup_ip_limiter.hit(ip_key)

    conflict = _name_conflict_response(values)
    if conflict is not None:
        audit("company_signup_name_conflict", domain=values["domain"])
        return conflict

    if Company.query.filter_by(email_domain=values["domain"]).first():
        audit("company_signup_domain_claimed", domain=values["domain"])
        return jsonify(
            {
                "error": (
                    f"Die Domain '{values['domain']}' ist bereits einer "
                    "Firma zugeordnet."
                )
            }
        ), 400

    email = values["email"]
    # E-mail conflicts are answered generically: nobody learns whether a
    # foreign address is already registered or pending.
    email_conflict = (
        UserRouting.query.filter(
            or_(
                func.lower(UserRouting.company_email) == email,
                func.lower(UserRouting.private_email) == email,
                func.lower(UserRouting.school_email) == email,
            )
        ).first()
        or CompanySignup.query.filter(
            func.lower(CompanySignup.email) == email
        ).first()
    )
    if email_conflict is not None:
        audit("company_signup_email_conflict")
        return _generic_response()

    signup = CompanySignup(
        name=values["name"],
        surname=values["surname"],
        job_title=values["job_title"],
        email=email,
        email_domain=values["domain"],
        company_name=values["company_name"],
        address=values["address"],
        password_hash=values["password_hash"],
        status=CompanySignup.STATUS_PENDING,
    )
    ttl_hours = int(current_app.config.get("SIGNUP_TOKEN_TTL_HOURS") or 24)
    token = company_signup_apply_token(
        signup, _utcnow() + timedelta(hours=ttl_hours)
    )
    db.session.add(signup)
    try:
        db.session.flush()
    except Exception:
        # Concurrent registration of the same address (unique constraint).
        db.session.rollback()
        audit("company_signup_email_conflict")
        return _generic_response()

    mail_error = _send_verification(signup, token, resend=False)
    if mail_error is not None:
        return mail_error

    return _generic_response()


@bp.route("/resend", methods=["POST"])
def resend():
    guard = _enabled_or_403()
    if guard is not None:
        return guard

    data = request.get_json(silent=True) or {}
    ip_key = f"ip:{request.remote_addr or 'unknown'}"
    limited = _rate_limited(signup_resend_ip_limiter, ip_key)
    if limited is not None:
        return limited

    email = (parse_str(data.get("email"), "E-Mail", allow_none=True) or "").strip().lower()
    signup = _active_pending_signup(email)
    if signup is None:
        # Generic on purpose: no information about existing signups leaks
        # here. An existing (possibly expired) signup is resendable below:
        # a re-sent token refreshes its validity.
        audit("company_signup_resend_noop")
        return _generic_response()

    email_key = f"email:{signup.email}"
    limited = _rate_limited(signup_resend_limiter, email_key)
    if limited is not None:
        return limited
    signup_resend_limiter.hit(email_key)

    ttl_hours = int(current_app.config.get("SIGNUP_TOKEN_TTL_HOURS") or 24)
    token = company_signup_apply_token(
        signup, _utcnow() + timedelta(hours=ttl_hours)
    )
    mail_error = _send_verification(signup, token, resend=True)
    if mail_error is not None:
        return mail_error
    return _generic_response()


def _provision_company(signup):
    """Create the tenant for a verified signup. Returns the payload for the
    response plus the session identifiers (user_id, company_id).

    Raises ValueError for permanent conflicts (nothing created yet, signup
    becomes failed) and ProvisionError after internal failures (tenant
    folder cleaned up, signup stays pending and can be retried).
    """
    # Deferred import: backend.companies imports the app entry point (CLI
    # helper `python -m backend.companies`), a top-level import would cycle.
    from backend import companies

    # Re-check e-mail conflicts: the global routing index may have gained a
    # matching account since the signup was submitted.
    email = signup.email
    if (
        UserRouting.query.filter(
            or_(
                func.lower(UserRouting.company_email) == email,
                func.lower(UserRouting.private_email) == email,
                func.lower(UserRouting.school_email) == email,
            )
        ).first()
    ):
        raise ValueError("Diese E-Mail-Adresse wird bereits verwendet.")

    # Performs all name/domain collision checks itself (the registry may
    # have changed since submit); commits the registry row.
    company = companies.add_company(
        signup.company_name, signup.email_domain, signup.address
    )

    try:
        tenants.create_company_schema(company)
    except Exception:
        tenants.reset_engine_cache()
        shutil.rmtree(tenants.company_base_dir(company), ignore_errors=True)
        db.session.rollback()
        stale = db.session.get(Company, company.id)
        if stale is not None:
            db.session.delete(stale)
            db.session.commit()
        raise ProvisionError("tenant schema provisioning failed") from None

    try:
        with tenants.tenant_context(company):
            user = User(
                role="admin",
                name=signup.name,
                surname=signup.surname,
                company_id=company.id,
                password_hash=signup.password_hash,
                company_address=signup.address or company.address or "",
                company_email=signup.email,
                job_title=signup.job_title,
            )
            db.session.add(user)
            db.session.flush()
            sync_user_routing(user)
            db.session.commit()
            # Complete the signup and collect the response payload while the
            # tenant context is active (objects refresh from the tenant DB).
            signup.status = CompanySignup.STATUS_COMPLETED
            signup.completed_at = _utcnow()
            db.session.commit()
            payload_user = serialize_user(user, user)
            ids = {
                "user_id": int(user.id),
                "company_id": int(company.id),
                "session_version": int(user.session_version or 0),
            }
    except Exception:
        # Never leave a half-provisioned tenant behind: remove folder,
        # cached engine and registry row; the signup stays pending so a
        # repeat verification can retry.
        try:
            tenants.reset_engine_cache()
            shutil.rmtree(tenants.company_base_dir(company), ignore_errors=True)
        except (OSError, ValueError, RuntimeError):
            pass
        db.session.rollback()
        stale = db.session.get(Company, company.id)
        if stale is not None:
            db.session.delete(stale)
            db.session.commit()
        raise ProvisionError("tenant provisioning failed") from None

    return payload_user, ids


@bp.route("/verify", methods=["POST"])
def verify():
    guard = _enabled_or_403()
    if guard is not None:
        return guard

    data = request.get_json(silent=True) or {}
    token = (parse_str(data.get("token"), "Token", default="") or "").strip()
    ip_key = f"ip:{request.remote_addr or 'unknown'}"

    limited = _rate_limited(verify_ip_limiter, ip_key)
    if limited is not None:
        return limited

    if not token or len(token) > 128 or any(c.isspace() for c in token):
        verify_ip_limiter.hit(ip_key)
        audit("company_signup_verify_invalid")
        return jsonify(
            {"error": "Der Bestätigungslink ist ungültig oder abgelaufen."}
        ), 400

    token_key = f"token:{hashlib.sha256(token.encode('utf-8')).hexdigest()}"
    limited = _rate_limited(verify_token_limiter, token_key)
    if limited is not None:
        return limited
    verify_token_limiter.hit(token_key)
    verify_ip_limiter.hit(ip_key)

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    signup = CompanySignup.query.filter_by(token_hash=token_hash).first()
    if signup is None or signup.status != CompanySignup.STATUS_PENDING:
        audit("company_signup_verify_invalid")
        return jsonify(
            {"error": "Der Bestätigungslink ist ungültig oder bereits verwendet."}
        ), 400
    if signup.is_expired():
        audit("company_signup_verify_expired")
        return jsonify(
            {
                "error": (
                    "Der Bestätigungslink ist abgelaufen. Bitte fordern Sie "
                    "eine neue Bestätigungs-E-Mail an."
                )
            }
        ), 400

    try:
        payload_user, ids = _provision_company(signup)
    except ValueError as exc:
        # Permanent conflict (e.g. domain claimed meanwhile): kill signup.
        db.session.rollback()
        failed = db.session.get(CompanySignup, signup.id)
        if failed is not None:
            failed.status = CompanySignup.STATUS_FAILED
            db.session.commit()
        audit("company_signup_provision_failed", reason="conflict")
        return jsonify({"error": str(exc)}), 409
    except ProvisionError:
        db.session.rollback()
        audit("company_signup_provision_failed", reason="internal")
        return jsonify(
            {
                "error": (
                    "Die Firma konnte nicht angelegt werden. Bitte "
                    "versuchen Sie es später erneut oder wenden Sie sich "
                    "an kontakt@lehrjahre.ch."
                )
            }
        ), 500

    session.clear()
    session.permanent = True
    session["user_id"] = ids["user_id"]
    session["company_id"] = ids["company_id"]
    session["session_version"] = ids["session_version"]
    csrf_token = ensure_csrf_token()
    audit(
        "company_signup_verified",
        user_id=ids["user_id"],
        company_id=ids["company_id"],
        domain=signup.email_domain,
    )
    return jsonify(
        {
            "data": {
                "user": payload_user,
                "csrf_token": csrf_token,
                "mem_professions": current_app.config["MEM_PROFESSIONS"],
                "trainer_functions": current_app.config["TRAINER_FUNCTIONS"],
            }
        }
    )
