from flask import Blueprint, request, jsonify
from backend.models import db, Participation, Project
from backend.auth import login_required, get_current_user, can_access_student
from backend.policies import (
    is_supervisor,
    is_student,
    supervised_student_ids,
    visible_project_ids_for,
    can_view_project,
)

bp = Blueprint("api_implementation", __name__, url_prefix="/api/implementation")


@bp.route("", methods=["GET"])
@login_required
def list_implementations():
    actor = get_current_user()
    student_id = request.args.get("student", type=int)
    project_id = request.args.get("project", type=int)

    visible_pids = visible_project_ids_for(actor)
    if not visible_pids:
        return jsonify({"data": []})

    query = Participation.query.filter(Participation.project.in_(visible_pids))

    if is_student(actor):
        if student_id and student_id != actor.id:
            return jsonify({"error": "Keine Berechtigung."}), 403
        query = query.filter_by(student=actor.id)
    elif student_id:
        if not can_access_student(actor, student_id):
            return jsonify({"error": "Keine Berechtigung."}), 403
        query = query.filter_by(student=student_id)
    else:
        sub_ids = supervised_student_ids(actor)
        if not sub_ids:
            return jsonify({"data": []})
        query = query.filter(Participation.student.in_(sub_ids))

    if project_id:
        query = query.filter_by(project=project_id)

    items = query.order_by(Participation.id.desc()).all()
    return jsonify({"data": [item.to_dict() for item in items]})


@bp.route("", methods=["POST"])
@login_required
def create_implementation():
    actor = get_current_user()
    if not is_student(actor):
        return jsonify(
            {
                "error": "Arbeitsberichte (Projektdurchführung) können nur von Lernenden erfasst werden."
            }
        ), 403

    data = request.get_json(silent=True) or {}
    project_id = data.get("project")
    title = (data.get("title") or "").strip()
    if not project_id or not title:
        return jsonify({"error": "Projekt und Titel sind erforderlich."}), 400

    project = db.session.get(Project, int(project_id))
    if not project or not can_view_project(actor, project):
        return jsonify({"error": "Projekt nicht gefunden oder nicht freigegeben."}), 404

    part = Participation(
        supervisor=project.author,
        student=actor.id,
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

    if not can_access_student(actor, part.student) or not can_view_project(
        actor, part.project_rel
    ):
        return jsonify({"error": "Keine Berechtigung."}), 403

    data = request.get_json(silent=True) or {}

    if is_student(actor):
        if part.is_done:
            return jsonify(
                {
                    "error": "Abgegebene Arbeitsberichte können von Lernenden nicht mehr bearbeitet oder wieder geöffnet werden."
                }
            ), 403
        if "title" in data and data["title"].strip():
            part.title = data["title"].strip()
        if "text" in data:
            part.text = (data.get("text") or "").strip()
        if "is_done" in data and bool(data.get("is_done")):
            part.is_done = True
    elif is_supervisor(actor):
        # Supervisors can only view the report content, but can change submission status (is_done)
        has_title_change = (
            "title" in data and data["title"].strip() != part.title
        )
        has_text_change = (
            "text" in data and (data.get("text") or "").strip() != (part.text or "")
        )
        if has_title_change or has_text_change:
            return jsonify(
                {
                    "error": "Die Projektdurchführung kann von Vorgesetzten nur angezeigt werden."
                }
            ), 403
        if "is_done" in data:
            part.is_done = bool(data.get("is_done"))
        if "supervisor" in data:
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

    if not is_student(actor) or part.student != actor.id:
        return jsonify({"error": "Keine Berechtigung."}), 403
    if part.is_done:
        return jsonify(
            {"error": "Abgegebene Arbeitsberichte können nicht gelöscht werden."}
        ), 403

    db.session.delete(part)
    db.session.commit()
    return jsonify({"data": {"deleted": part_id}})
