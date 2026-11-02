from datetime import date
from flask import Blueprint, request, jsonify
from backend.models import db, User, UserRelation
from backend.auth import (
    login_required,
    role_required,
    get_current_user,
    hash_password,
    verify_password,
    is_admin_or_hr,
)

bp = Blueprint("api_user", __name__, url_prefix="/api/user")


def parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


@bp.route("", methods=["GET"])
@login_required
def list_users():
    actor = get_current_user()
    role_filter = request.args.get("role")

    query = User.query.filter_by(company=actor.company)
    if role_filter in {"lernender", "ausbildner"}:
        query = query.filter_by(role=role_filter)

    users = query.order_by(User.start_date.desc().nullslast(), User.id.desc()).all()
    relations = (
        UserRelation.query.join(User, UserRelation.student == User.id)
        .filter(User.company == actor.company)
        .all()
    )

    return jsonify(
        {
            "data": {
                "users": [u.to_dict() for u in users],
                "relations": [r.to_dict() for r in relations],
            }
        }
    )


@bp.route("/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    actor = get_current_user()
    target = db.session.get(User, user_id)
    if not target or target.company != actor.company:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    supervisors = UserRelation.query.filter_by(student=target.id).all()
    students = UserRelation.query.filter_by(supervisor=target.id).all()

    data = target.to_dict()
    data["supervisors"] = [r.to_dict() for r in supervisors]
    data["students"] = [r.to_dict() for r in students]
    return jsonify({"data": data})


@bp.route("", methods=["POST"])
@role_required("ausbildner")
def create_user():
    actor = get_current_user()
    if not is_admin_or_hr(actor):
        return jsonify(
            {"error": "Nur Administratoren, Berufsbildner oder HR dürfen Benutzer anlegen."}
        ), 403

    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "lernender").strip().lower()
    if role not in {"lernender", "ausbildner"}:
        return jsonify({"error": "Ungültige Rolle."}), 400

    name = (data.get("name") or "").strip()
    surname = (data.get("surname") or "").strip()
    company_email = (data.get("company_email") or "").strip().lower()
    job_title = (data.get("job_title") or "").strip()
    password = data.get("password") or "Lehrjahre2026!"

    if not name or not surname or not company_email or not job_title:
        return jsonify(
            {"error": "Vorname, Nachname, Firmen-E-Mail und Beruf/Funktion sind Pflichtfelder."}
        ), 400

    if User.query.filter(User.company_email.ilike(company_email)).first():
        return jsonify({"error": "Diese Firmen-E-Mail wird bereits verwendet."}), 400

    new_user = User(
        role=role,
        name=name,
        surname=surname,
        company=(data.get("company") or actor.company).strip(),
        password_hash=hash_password(password),
        private_address=(data.get("private_address") or "").strip(),
        private_email=(data.get("private_email") or "").strip(),
        private_phone=(data.get("private_phone") or "").strip(),
        school_address=(data.get("school_address") or "").strip(),
        school_email=(data.get("school_email") or "").strip(),
        school_phone=(data.get("school_phone") or "").strip(),
        company_address=(data.get("company_address") or "").strip(),
        company_email=company_email,
        company_phone=(data.get("company_phone") or "").strip(),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        job_title=job_title,
        picture_document=data.get("picture_document"),
    )
    db.session.add(new_user)
    db.session.commit()

    # Optional initial supervisor relation
    supervisor_id = data.get("supervisor_id")
    if role == "lernender" and supervisor_id:
        sup = db.session.get(User, int(supervisor_id))
        if sup and sup.company == new_user.company and sup.role == "ausbildner":
            db.session.add(UserRelation(supervisor=sup.id, student=new_user.id))
            db.session.commit()

    return jsonify({"data": new_user.to_dict()}), 201


@bp.route("/<int:user_id>", methods=["PUT"])
@login_required
def update_user(user_id):
    actor = get_current_user()
    target = db.session.get(User, user_id)
    if not target or target.company != actor.company:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    if actor.id != target.id and not is_admin_or_hr(actor):
        return jsonify({"error": "Keine Berechtigung zur Bearbeitung dieses Profils."}), 403

    data = request.get_json(silent=True) or {}

    # Contact fields editable by user themselves or admin/HR
    contact_fields = [
        "private_address",
        "private_email",
        "private_phone",
        "school_address",
        "school_email",
        "school_phone",
        "company_address",
        "company_phone",
    ]
    for field in contact_fields:
        if field in data:
            setattr(target, field, (data.get(field) or "").strip())

    if "picture_document" in data:
        target.picture_document = data.get("picture_document")

    # Admin / HR / Berufsbildner can also update core profile fields
    if is_admin_or_hr(actor):
        if "name" in data and data["name"]:
            target.name = data["name"].strip()
        if "surname" in data and data["surname"]:
            target.surname = data["surname"].strip()
        if "job_title" in data and data["job_title"]:
            target.job_title = data["job_title"].strip()
        if "role" in data and data["role"] in {"lernender", "ausbildner"}:
            target.role = data["role"]
        if "company_email" in data and data["company_email"]:
            new_email = data["company_email"].strip().lower()
            existing = User.query.filter(
                User.company_email.ilike(new_email), User.id != target.id
            ).first()
            if existing:
                return jsonify({"error": "Firmen-E-Mail bereits vergeben."}), 400
            target.company_email = new_email
        if "start_date" in data:
            target.start_date = parse_date(data.get("start_date"))
        if "end_date" in data:
            target.end_date = parse_date(data.get("end_date"))

    # Password update
    if data.get("new_password"):
        new_pw = data["new_password"]
        if len(new_pw) < 8:
            return jsonify(
                {"error": "Das neue Passwort muss mindestens 8 Zeichen lang sein."}
            ), 400
        if actor.id == target.id and not is_admin_or_hr(actor):
            current_pw = data.get("current_password") or ""
            if not verify_password(target.password_hash, current_pw):
                return jsonify({"error": "Das aktuelle Passwort ist falsch."}), 400
        elif actor.id == target.id and data.get("current_password"):
            if not verify_password(target.password_hash, data["current_password"]):
                return jsonify({"error": "Das aktuelle Passwort ist falsch."}), 400
        target.password_hash = hash_password(new_pw)

    db.session.commit()
    return jsonify({"data": target.to_dict()})


@bp.route("/<int:user_id>", methods=["DELETE"])
@role_required("ausbildner")
def delete_user(user_id):
    actor = get_current_user()
    if not is_admin_or_hr(actor):
        return jsonify({"error": "Keine Berechtigung."}), 403
    if actor.id == user_id:
        return jsonify({"error": "Das eigene Konto kann nicht gelöscht werden."}), 400

    target = db.session.get(User, user_id)
    if not target or target.company != actor.company:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    db.session.delete(target)
    db.session.commit()
    return jsonify({"data": {"deleted": user_id}})


@bp.route("/relation", methods=["POST"])
@role_required("ausbildner")
def add_relation():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}
    supervisor_id = data.get("supervisor")
    student_id = data.get("student")

    if not supervisor_id or not student_id:
        return jsonify({"error": "Ausbildner und Lernender sind erforderlich."}), 400

    sup = db.session.get(User, int(supervisor_id))
    stu = db.session.get(User, int(student_id))
    if not sup or not stu or sup.company != actor.company or stu.company != actor.company:
        return jsonify({"error": "Ungültige Benutzerzuordnung."}), 400

    existing = UserRelation.query.filter_by(
        supervisor=sup.id, student=stu.id
    ).first()
    if existing:
        return jsonify({"data": existing.to_dict()})

    rel = UserRelation(supervisor=sup.id, student=stu.id)
    db.session.add(rel)
    db.session.commit()
    return jsonify({"data": rel.to_dict()}), 201


@bp.route("/relation/<int:relation_id>", methods=["DELETE"])
@role_required("ausbildner")
def remove_relation(relation_id):
    actor = get_current_user()
    rel = db.session.get(UserRelation, relation_id)
    if not rel:
        return jsonify({"error": "Zuordnung nicht gefunden."}), 404

    stu = db.session.get(User, rel.student)
    if not stu or stu.company != actor.company:
        return jsonify({"error": "Keine Berechtigung."}), 403

    db.session.delete(rel)
    db.session.commit()
    return jsonify({"data": {"deleted": relation_id}})
