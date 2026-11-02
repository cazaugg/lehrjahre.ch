from flask import Blueprint, request, jsonify
from backend.models import db, Participation, Project, User
from backend.auth import login_required, get_current_user, can_access_student

bp = Blueprint("api_implementation", __name__, url_prefix="/api/implementation")


@bp.route("", methods=["GET"])
@login_required
def list_implementations():
    actor = get_current_user()
    student_id = request.args.get("student", type=int)
    project_id = request.args.get("project", type=int)

    if actor.role == "lernender":
        student_id = actor.id

    query = Participation.query
    if student_id:
        if not can_access_student(actor, student_id):
            return jsonify({"error": "Keine Berechtigung."}), 403
        query = query.filter_by(student=student_id)
    else:
        company_student_ids = [
            u.id
            for u in User.query.filter_by(
                company=actor.company, role="lernender"
            ).all()
        ]
        query = query.filter(Participation.student.in_(company_student_ids))

    if project_id:
        query = query.filter_by(project=project_id)

    items = query.order_by(Participation.id.desc()).all()
    return jsonify({"data": [item.to_dict() for item in items]})


@bp.route("", methods=["POST"])
@login_required
def create_implementation():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}

    project_id = data.get("project")
    title = (data.get("title") or "").strip()
    if not project_id or not title:
        return jsonify({"error": "Projekt und Titel sind erforderlich."}), 400

    project = db.session.get(Project, int(project_id))
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    student_id = data.get("student") if actor.role == "ausbildner" else actor.id
    if not student_id:
        return jsonify({"error": "Lernende/r muss angegeben werden."}), 400

    student_id = int(student_id)
    if not can_access_student(actor, student_id):
        return jsonify({"error": "Keine Berechtigung für diese/n Lernende/n."}), 403

    supervisor_id = data.get("supervisor")
    if not supervisor_id and actor.role == "ausbildner":
        supervisor_id = actor.id

    part = Participation(
        supervisor=int(supervisor_id) if supervisor_id else None,
        student=student_id,
        project=project.id,
        title=title,
        text=(data.get("text") or "").strip(),
        is_done=bool(data.get("is_done", False)),
    )
    db.session.add(part)
    db.session.commit()
    return jsonify({"data": part.to_dict()}), 201


@bp.route("/<int:part_id>", methods=["PUT"])
@login_required
def update_implementation(part_id):
    actor = get_current_user()
    part = db.session.get(Participation, part_id)
    if not part:
        return jsonify({"error": "Aufgabe / Bericht nicht gefunden."}), 404

    if not can_access_student(actor, part.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"].strip():
        part.title = data["title"].strip()
    if "text" in data:
        part.text = (data.get("text") or "").strip()
    if "is_done" in data:
        part.is_done = bool(data.get("is_done"))
    if actor.role == "ausbildner" and "supervisor" in data:
        part.supervisor = int(data["supervisor"]) if data["supervisor"] else None

    db.session.commit()
    return jsonify({"data": part.to_dict()})


@bp.route("/<int:part_id>", methods=["DELETE"])
@login_required
def delete_implementation(part_id):
    actor = get_current_user()
    part = db.session.get(Participation, part_id)
    if not part:
        return jsonify({"error": "Eintrag nicht gefunden."}), 404

    if not can_access_student(actor, part.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    db.session.delete(part)
    db.session.commit()
    return jsonify({"data": {"deleted": part_id}})
