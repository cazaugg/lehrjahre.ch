import hashlib
from datetime import date
from datetime import datetime, timedelta, timezone as dt_timezone
from sqlalchemy import func
from flask import Blueprint, request, jsonify, g, session, current_app
from backend import tenants
from backend.models import (
    db,
    Company,
    User,
    UserRelation,
    UserRouting,
    Project,
    Documents,
    user_apply_invite,
    user_clear_invite,
    INVITED_PASSWORD_HASH,
)
from backend.auth import (
    login_required,
    role_required,
    get_current_user,
    hash_password,
    verify_password,
    bump_session_version,
    ensure_csrf_token,
)
from backend.mail import MailDeliveryError, send_user_invite
from backend.audit import audit
from backend.ratelimit import invite_ip_limiter, invite_token_limiter
from backend.storage import delete_stored_file
from backend.policies import (
    is_supervisor,
    is_admin,
    supervised_student_ids,
    can_edit_user_contacts,
    can_edit_student_master_data,
    serialize_user,
)
from backend.validation import parse_int, parse_str

bp = Blueprint("api_user", __name__, url_prefix="/api/user")

MAX_PASSWORD_LEN = 512


def _utcnow():
    """SQLite drops timezones on DateTime round-trips; use naive UTC."""
    return datetime.now(dt_timezone.utc).replace(tzinfo=None)


def _new_invite_token(user) -> str:
    """Bind a fresh one-time invitation token; caller persists (commit)."""
    ttl_hours = int(current_app.config.get("USER_INVITE_TTL_HOURS") or 168)
    return user_apply_invite(user, _utcnow() + timedelta(hours=ttl_hours))


def _send_invite_mail(user, company, token: str, resent: bool = False) -> bool:
    """Mail the invitation link for `token` to the user's company address.

    Invitations are always sent to company e-mails: the address is bound to
    the (mailbox-proven) company domain and a free-text private address can
    never be an ownership guarantee.

    Returns whether the mail could NOT be delivered (already audited).
    """
    base_url = current_app.config.get("LEHRJAHRE_PUBLIC_URL") or ""
    verify_url = f"{base_url}/einladung?token={token}&c={company.id}"
    try:
        send_user_invite(
            user.company_email,
            f"{user.name} {user.surname}".strip(),
            company.name,
            verify_url,
        )
    except MailDeliveryError:
        audit(
            "user_invite_mail_failed",
            user_id=user.id,
            company_id=user.company_id,
            resent=resent,
        )
        return True
    audit(
        "user_invite_created",
        user_id=user.id,
        company_id=user.company_id,
        resent=resent,
    )
    return False
    try:
        send_user_invite(
            user.company_email,
            f"{user.name} {user.surname}".strip(),
            company.name,
            verify_url,
        )
    except MailDeliveryError:
        audit(
            "user_invite_mail_failed",
            user_id=user.id,
            company_id=user.company_id,
        )
        return True
    audit(
        "user_invite_created",
        user_id=user.id,
        company_id=user.company_id,
        resent=False,
    )
    return False

CONTACT_FIELDS = [
    "private_address",
    "private_email",
    "private_phone",
    "school_address",
    "school_email",
    "school_phone",
    "company_address",
    "company_phone",
]

MASTER_FIELDS = [
    "name",
    "surname",
    "job_title",
    "role",
    "company_email",
    "start_date",
    "end_date",
]


def _invalidate_supervised_cache():
    if hasattr(g, "_supervised_student_ids"):
        delattr(g, "_supervised_student_ids")


def _validated_relation_pair(supervisor_id: int, student_id: int, actor: User):
    """Return (supervisor, student, error) for a relation pair write.

    Supervisors may assign themselves or peers, but the pair must always be
    a same-company ausbildner -> lernender link, and never a self-pair.
    """
    error = "Ungültige Benutzerzuordnung."
    if supervisor_id == student_id:
        return None, None, "Eine Zugordnung zwischen zwei Ausbildnern oder einer Person mit sich selbst ist nicht zulässig."
    sup = db.session.get(User, supervisor_id)
    stu = db.session.get(User, student_id)
    if (
        not sup
        or not stu
        or sup.company_id != actor.company_id
        or stu.company_id != actor.company_id
    ):
        return None, None, error
    if sup.role not in ("ausbildner", "admin") or stu.role != "lernender":
        return None, None, error
    return sup, stu, None


def parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def sync_user_routing(user: User) -> None:
    """Mirror the login routing row into the control database.

    Called with the tenant user already flushed so its id/emails are known.
    The routing row enables the global login e-mail search; all other user
    data stays exclusively in the company database.
    """
    routing = UserRouting.query.filter_by(
        id=user.id, company_id=user.company_id
    ).first()
    if routing is None:
        routing = UserRouting(id=user.id, company_id=user.company_id)
        db.session.add(routing)
    routing.company_email = user.company_email
    routing.private_email = user.private_email or ""
    routing.school_email = user.school_email or ""


def drop_user_routing(user: User) -> None:
    """Remove the control-DB routing row of a deleted user."""
    routing = UserRouting.query.filter_by(
        id=user.id, company_id=user.company_id
    ).first()
    if routing is not None:
        db.session.delete(routing)


@bp.route("", methods=["GET"])
@login_required
def list_users():
    actor = get_current_user()
    role_filter = request.args.get("role")
    subordinate_only = request.args.get("subordinate_only") == "true"

    query = User.query.filter_by(company_id=actor.company_id)
    if role_filter in {"lernender", "ausbildner", "admin"}:
        query = query.filter_by(role=role_filter)
    if subordinate_only and is_supervisor(actor):
        query = query.filter(User.id.in_(supervised_student_ids(actor)))

    users = query.order_by(User.start_date.desc().nullslast(), User.id.desc()).all()
    relations = (
        UserRelation.query.join(User, UserRelation.student == User.id)
        .filter(User.company_id == actor.company_id)
        .all()
    )

    return jsonify(
        {
            "data": {
                "users": [serialize_user(u, actor) for u in users],
                "relations": [r.to_dict() for r in relations],
            }
        }
    )


@bp.route("/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    actor = get_current_user()
    target = db.session.get(User, user_id)
    if not target or target.company_id != actor.company_id:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    supervisors = UserRelation.query.filter_by(student=target.id).all()
    students = UserRelation.query.filter_by(supervisor=target.id).all()

    data = serialize_user(target, actor)
    data["supervisors"] = [r.to_dict() for r in supervisors]
    data["students"] = [r.to_dict() for r in students]
    return jsonify({"data": data})


@bp.route("", methods=["POST"])
@role_required("admin")
def create_user():
    actor = get_current_user()
    company = tenants.current_company()

    data = request.get_json(silent=True) or {}
    raw_role = parse_str(data.get("role"), "Rolle", default="lernender")
    role = raw_role.lower()
    if raw_role != role or role not in {"lernender", "ausbildner", "admin"}:
        return jsonify({"error": "Ungültige Rolle."}), 400

    if "password" in data:
        return jsonify(
            {
                "error": (
                    "Das Passwort wird von der Person selbst per "
                    "Einladungs-E-Mail gesetzt."
                )
            }
        ), 400

    name = parse_str(data.get("name"), "Vorname")
    surname = parse_str(data.get("surname"), "Nachname")
    company_email = parse_str(data.get("company_email"), "Firmen-E-Mail").lower()
    job_title = parse_str(data.get("job_title"), "Beruf/Funktion")

    if not name or not surname or not company_email or not job_title:
        return jsonify(
            {
                "error": "Vorname, Nachname, Firmen-E-Mail und Beruf/Funktion sind Pflichtfelder."
            }
        ), 400

    if not company or not company.matches_email(company_email):
        domain = company.email_domain if company else ""
        return jsonify(
            {
                "error": (
                    f"Die Firmen-E-Mail muss zur Domain @{domain} gehören."
                    if domain
                    else "Für den Benutzer ist keine Firma hinterlegt."
                )
            }
        ), 400

    # The routing index in the control DB spans all companies: a login e-mail
    # must be unique across the whole platform, not only within this company.
    if (
        UserRouting.query.filter(
            func.lower(UserRouting.company_email) == company_email
        ).first()
        or User.query.filter(User.company_email.ilike(company_email)).first()
    ):
        return jsonify({"error": "Diese Firmen-E-Mail wird bereits verwendet."}), 400

    company_address = parse_str(data.get("company_address"), "Firmenadresse")
    if not company_address:
        company_address = (company.address or "").strip()

    supervisor_id = parse_int(
        data.get("supervisor_id"), "Vorgesetzter", allow_none=True, min_value=1
    )

    new_user = User(
        role=role,
        name=name,
        surname=surname,
        company_id=actor.company_id,
        # Unusable stand-in hash: the person sets their own password via the
        # invitation link (see invite_accept). Keeps login timing identical.
        password_hash=INVITED_PASSWORD_HASH,
        private_address=parse_str(data.get("private_address"), "Private Adresse"),
        private_email=parse_str(data.get("private_email"), "Private E-Mail"),
        private_phone=parse_str(data.get("private_phone"), "Private Telefonnummer"),
        school_address=parse_str(data.get("school_address"), "Schuladresse"),
        school_email=parse_str(data.get("school_email"), "Schul-E-Mail"),
        school_phone=parse_str(data.get("school_phone"), "Schul-Telefonnummer"),
        company_address=company_address,
        company_email=company_email,
        company_phone=parse_str(data.get("company_phone"), "Firmen-Telefonnummer"),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        job_title=job_title,
        # A profile picture can only reference an existing document owned by
        # this user; that is set after the account exists via PUT /api/user.
        picture_document=None,
    )
    db.session.add(new_user)
    db.session.flush()  # assigns the tenant id shared by the routing row
    sync_user_routing(new_user)
    # The token is persisted before the mail goes out: a sent link always
    # matches the stored hash.
    invite_token = _new_invite_token(new_user)
    db.session.commit()
    mail_failed = _send_invite_mail(new_user, company, invite_token)
    audit(
        "user_created",
        user_id=new_user.id,
        role=role,
        company_id=new_user.company_id,
        role_elevation=bool(role in {"ausbildner", "admin"}),
    )

    # Optional initial supervisor relation
    if role == "lernender" and supervisor_id:
        sup, _stu, relation_error = _validated_relation_pair(
            supervisor_id, new_user.id, actor
        )
        if relation_error:
            return jsonify({"error": relation_error}), 400
        db.session.add(UserRelation(supervisor=sup.id, student=new_user.id))
        db.session.commit()
        audit(
            "relation_added",
            supervisor_id=sup.id,
            student_id=new_user.id,
            self_assigned=bool(sup.id == actor.id),
        )
        _invalidate_supervised_cache()

    payload = serialize_user(new_user, actor)
    if mail_failed:
        payload["invite_mail_failed"] = True
    return jsonify({"data": payload}), 201


@bp.route("/invite/accept", methods=["POST"])
def invite_accept():
    """First-login invitation: the token holder sets their own password and
    is logged in. Unauthenticated; the one-time token is the capability."""
    data = request.get_json(silent=True) or {}

    ip_key = f"ip:{request.remote_addr or 'unknown'}"
    limited = _invite_rate_limited(invite_ip_limiter, ip_key)
    if limited is not None:
        return limited

    token = (parse_str(data.get("token"), "Token", default="") or "").strip()
    company_id = parse_int(
        data.get("company_id"), "Firma", allow_none=True, min_value=1
    )
    password = parse_str(
        data.get("password"), "Passwort", default="", strip=False
    )

    invalid_response = jsonify(
        {"error": "Der Einladungslink ist ungültig oder bereits verwendet."}
    ), 400

    if not token or len(token) > 128 or any(c.isspace() for c in token):
        invite_ip_limiter.hit(ip_key)
        audit("user_invite_invalid")
        return invalid_response

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    token_key = f"token:{token_hash}"
    limited = _invite_rate_limited(invite_token_limiter, token_key)
    if limited is not None:
        return limited
    invite_token_limiter.hit(token_key)
    invite_ip_limiter.hit(ip_key)

    if company_id is None:
        audit("user_invite_invalid")
        return invalid_response

    if password_errors := _validate_password(password):
        return jsonify({"error": password_errors}), 400

    company = db.session.get(Company, int(company_id))
    if company is None:
        audit("user_invite_invalid")
        return invalid_response

    # Login activation runs entirely inside the company database.
    with tenants.tenant_context(company):
        user = User.query.filter(User.invite_token_hash == token_hash).first()
        if user is None or not user.invite_expires_at:
            audit("user_invite_invalid")
            return invalid_response
        if _utcnow() >= user.invite_expires_at:
            audit("user_invite_expired")
            return jsonify(
                {
                    "error": (
                        "Der Einladungslink ist abgelaufen. Bitten Sie Ihre "
                        "Verwaltung, die Einladung erneut zu senden."
                    )
                }
            ), 400

        user.password_hash = hash_password(password)
        user_clear_invite(user)
        bump_session_version(user)
        db.session.commit()
        payload_user = serialize_user(user, user)
        ids = {
            "user_id": int(user.id),
            "company_id": int(company.id),
            "session_version": int(user.session_version or 0),
        }

    session.clear()
    session.permanent = True
    session["user_id"] = ids["user_id"]
    session["company_id"] = ids["company_id"]
    session["session_version"] = ids["session_version"]
    csrf_token = ensure_csrf_token()
    audit("user_invite_accepted", user_id=ids["user_id"], company_id=company.id)
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


def _invite_rate_limited(limiter, key):
    retry_after = limiter.retry_after(key)
    if retry_after is not None:
        response = jsonify(
            {"error": "Zu viele Anfragen. Bitte später erneut versuchen."}
        )
        response.status_code = 429
        response.headers["Retry-After"] = str(max(1, int(retry_after)))
        return response
    return None


def _validate_password(password: str) -> str | None:
    if not password:
        return "Passwort ist erforderlich."
    if len(password) < 8:
        return "Das Passwort muss mindestens 8 Zeichen lang sein."
    if len(password) > MAX_PASSWORD_LEN:
        return "Das Passwort ist zu lang."
    if "\x00" in password:
        return "Das Passwort enthält ungültige Zeichen."
    return None


@bp.route("/<int:user_id>/invite/resend", methods=["POST"])
@role_required("admin")
def invite_resend(user_id):
    actor = get_current_user()
    target = db.session.get(User, user_id)
    if not target or target.company_id != actor.company_id:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    if not bool(target.invite_token_hash):
        return jsonify(
            {"error": "Diese Person hat bereits ein Passwort gesetzt."}
        ), 400

    company = tenants.current_company()
    # New token first (invalidates older links), persisted, then re-sent.
    invite_token = _new_invite_token(target)
    db.session.commit()
    mail_failed = _send_invite_mail(target, company, invite_token, resent=True)
    if mail_failed:
        return jsonify(
            {
                "error": (
                    "Die Einladungs-E-Mail konnte gerade nicht gesendet "
                    "werden. Bitte versuchen Sie es später erneut."
                )
            }
        ), 502
    return jsonify({"data": {"resent": target.id, "password_pending": True}})

@bp.route("/<int:user_id>", methods=["PUT"])
@login_required
def update_user(user_id):
    actor = get_current_user()
    target = db.session.get(User, user_id)
    if not target or target.company_id != actor.company_id:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    if actor.id != target.id and not can_edit_user_contacts(actor, target):
        return jsonify(
            {"error": "Keine Berechtigung zur Bearbeitung dieses Profils."}
        ), 403

    data = request.get_json(silent=True) or {}

    if "company_id" in data or "company" in data:
        return jsonify({"error": "Die Firma kann nicht geändert werden."}), 400

    # Check if caller attempts to update contact fields
    has_contact_edits = any(field in data for field in CONTACT_FIELDS)
    if has_contact_edits and not can_edit_user_contacts(actor, target):
        return jsonify(
            {"error": "Keine Berechtigung zur Bearbeitung der Kontaktangaben."}
        ), 403

    # Check if caller attempts to update master data fields
    # (Ignore company_email if passed unchanged by the disabled form field)
    incoming_company_email = parse_str(
        data.get("company_email"), "Firmen-E-Mail", allow_none=True
    )
    has_master_edits = any(
        field in data
        and not (
            field == "company_email"
            and (incoming_company_email or "").lower()
            == (target.company_email or "").lower()
        )
        for field in MASTER_FIELDS
    )
    if has_master_edits and not can_edit_student_master_data(actor, target):
        return jsonify(
            {"error": "Keine Berechtigung zur Bearbeitung der Stammdaten."}
        ), 403

    if has_contact_edits:
        for field in CONTACT_FIELDS:
            if field in data:
                setattr(target, field, parse_str(data.get(field), field))

    if "picture_document" in data:
        if actor.id != target.id and not can_edit_user_contacts(actor, target):
            return jsonify({"error": "Keine Berechtigung."}), 403
        raw_picture = data.get("picture_document")
        if raw_picture in (None, ""):
            target.picture_document = None
        else:
            try:
                picture_id = int(raw_picture)
            except (TypeError, ValueError):
                return jsonify({"error": "Ungültiges Profilbild."}), 400
            picture = db.session.get(Documents, picture_id)
            if (
                not picture
                or picture.type != "profilbild"
                or picture.owner != target.id
            ):
                return jsonify({"error": "Ungültiges Profilbild."}), 400
            target.picture_document = picture.id

    if has_master_edits and can_edit_student_master_data(actor, target):
        if "name" in data:
            name = parse_str(data.get("name"), "Vorname")
            if name:
                target.name = name
        if "surname" in data:
            surname = parse_str(data.get("surname"), "Nachname")
            if surname:
                target.surname = surname
        if "job_title" in data:
            job_title = parse_str(data.get("job_title"), "Beruf/Funktion")
            if job_title:
                target.job_title = job_title
        if "role" in data:
            role = parse_str(data.get("role"), "Rolle")
            if role != target.role:
                # Role changes (promotion or demotion, even of the actor
                # themselves) are exclusively an admin capability and must
                # be an explicit, audit-logged event. No silent role
                # escalation through master-data edits.
                if not is_admin(actor):
                    return jsonify(
                        {"error": "Rollen können nur von Administratoren geändert werden."}
                    ), 403
                if role not in {"lernender", "ausbildner", "admin"}:
                    return jsonify({"error": "Ungültige Rolle."}), 400
                if data.get("confirm_role_elevation") is not True:
                    return jsonify(
                        {
                            "error": "Rollenänderung erfordert confirm_role_elevation=true."
                        }
                    ), 403
                target.role = role
        if "company_email" in data and incoming_company_email:
            company = tenants.current_company()
            new_email = incoming_company_email.lower()
            if not company.matches_email(new_email):
                return jsonify(
                    {
                        "error": (
                            "Die Firmen-E-Mail muss zur Domain "
                            f"@{company.email_domain} gehören."
                        )
                    }
                ), 400
            # E-mails are unique across the whole platform (routing index).
            if (
                UserRouting.query.filter(
                    func.lower(UserRouting.company_email) == new_email,
                    UserRouting.id != target.id,
                ).first()
                or User.query.filter(
                    User.company_email.ilike(new_email), User.id != target.id
                ).first()
            ):
                return jsonify({"error": "Firmen-E-Mail bereits vergeben."}), 400
            target.company_email = new_email
        if "start_date" in data:
            target.start_date = parse_date(data.get("start_date"))
        if "end_date" in data:
            target.end_date = parse_date(data.get("end_date"))

    # Password update
    new_pw = parse_str(
        data.get("new_password"), "Neues Passwort", default="", strip=False
    )
    if new_pw:
        if len(new_pw) < 8:
            return jsonify(
                {"error": "Das neue Passwort muss mindestens 8 Zeichen lang sein."}
            ), 400
        if actor.id == target.id:
            current_pw = parse_str(
                data.get("current_password"),
                "Aktuelles Passwort",
                default="",
                strip=False,
            )
            if not verify_password(target.password_hash, current_pw):
                return jsonify({"error": "Das aktuelle Passwort ist falsch."}), 400
        elif not can_edit_student_master_data(actor, target):
            return jsonify({"error": "Keine Berechtigung."}), 403
        target.password_hash = hash_password(new_pw)
        bump_session_version(target)
        # Any outstanding invitation link dies once a password exists.
        user_clear_invite(target)

    sync_user_routing(target)
    db.session.commit()
    if new_pw and actor.id == target.id:
        # Keep the browser that changed its own password logged in; all other
        # sessions for this user have been invalidated by the version bump.
        session["session_version"] = int(target.session_version or 0)
    audit(
        "user_updated",
        user_id=target.id,
        password_changed=bool(new_pw),
        role=target.role,
        role_elevation=bool(
            actor.id != target.id and target.role == "ausbildner"
        ),
    )
    return jsonify({"data": serialize_user(target, actor)})


@bp.route("/<int:user_id>", methods=["DELETE"])
@role_required("admin")
def delete_user(user_id):
    actor = get_current_user()
    if actor.id == user_id:
        return jsonify({"error": "Das eigene Konto kann nicht gelöscht werden."}), 400

    target = db.session.get(User, user_id)
    if not target or target.company_id != actor.company_id:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    if target.role == "lernender" and not can_edit_student_master_data(actor, target):
        return jsonify({"error": "Keine Berechtigung."}), 403

    # Projects must keep an author in the company; never leave orphaned rows
    # that could later become visible across company boundaries.
    Project.query.filter_by(author=target.id).update(
        {Project.author: actor.id}, synchronize_session=False
    )

    # Document rows cascade with the user; collect the files first so they do
    # not remain on disk after the account is gone.
    document_paths = [
        document.path
        for document in Documents.query.filter_by(owner=target.id).all()
    ]

    deleted_role = target.role
    drop_user_routing(target)  # first: makes the account unreachable
    db.session.delete(target)
    db.session.commit()
    for path in document_paths:
        delete_stored_file(path)
    audit(
        "user_deleted",
        user_id=user_id,
        role=deleted_role,
        documents_deleted=len(document_paths),
    )
    return jsonify({"data": {"deleted": user_id}})


@bp.route("/relation", methods=["POST"])
@role_required("admin")
def add_relation():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}
    supervisor_id = parse_int(data.get("supervisor"), "Ausbildner", min_value=1)
    student_id = parse_int(data.get("student"), "Lernende/r", min_value=1)

    sup, stu, relation_error = _validated_relation_pair(
        supervisor_id, student_id, actor
    )
    if relation_error or not sup or not stu:
        return jsonify({"error": relation_error or "Ungültige Benutzerzuordnung."}), 400

    existing = UserRelation.query.filter_by(
        supervisor=sup.id, student=stu.id
    ).first()
    if existing:
        return jsonify({"data": existing.to_dict()})

    rel = UserRelation(supervisor=sup.id, student=stu.id)
    db.session.add(rel)
    db.session.commit()
    audit(
        "relation_added",
        supervisor_id=sup.id,
        student_id=stu.id,
        self_assigned=bool(sup.id == actor.id),
    )
    _invalidate_supervised_cache()
    return jsonify({"data": rel.to_dict()}), 201


@bp.route("/relation/<int:relation_id>", methods=["DELETE"])
@role_required("admin")
def remove_relation(relation_id):
    actor = get_current_user()
    rel = db.session.get(UserRelation, relation_id)
    if not rel:
        return jsonify({"error": "Zuordnung nicht gefunden."}), 404

    stu = db.session.get(User, rel.student)
    sup = db.session.get(User, rel.supervisor)
    if not stu or not sup or stu.company_id != actor.company_id or sup.company_id != actor.company_id:
        return jsonify({"error": "Keine Berechtigung."}), 403
    if sup.role not in ("ausbildner", "admin") or stu.role != "lernender":
        return jsonify({"error": "Keine Berechtigung."}), 403

    supervisor_id = rel.supervisor
    student_id = rel.student
    db.session.delete(rel)
    db.session.commit()
    audit(
        "relation_removed",
        supervisor_id=supervisor_id,
        student_id=student_id,
        self_assigned=bool(supervisor_id == actor.id),
    )
    _invalidate_supervised_cache()
    return jsonify({"data": {"deleted": relation_id}})


@bp.route("/relation", methods=["GET"])
@login_required
def list_relations():
    actor = get_current_user()
    supervisor_filter = request.args.get("supervisor", type=int)
    student_filter = request.args.get("student", type=int)

    query = UserRelation.query.join(User, UserRelation.student == User.id).filter(
        User.company_id == actor.company_id
    )
    if supervisor_filter is not None:
        query = query.filter(UserRelation.supervisor == supervisor_filter)
    if student_filter is not None:
        query = query.filter(UserRelation.student == student_filter)
    relations = query.order_by(UserRelation.id.asc()).all()
    return jsonify({"data": [r.to_dict() for r in relations]})
