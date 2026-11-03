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
    if actor.role != "lernender":
        return jsonify(
            {
                "error": "Die Durchführung wird ausschliesslich von Lernenden erfasst. Vorgesetzte haben Leserechte."
            }
        ), 403

    data = request.get_json(silent=True) or {}
    project_id = data.get("project")
    if not project_id:
        return jsonify({"error": "Projekt / Aufgabe ist erforderlich."}), 400

    project = db.session.get(Project, int(project_id))
    if not project:
        return jsonify({"error": "Projekt / Aufgabe nicht gefunden."}), 404

    root_project = (
        db.session.get(Project, project.parent_project)
        if project.parent_project
        else project
    )
    if not root_project or not root_project.is_published:
        return jsonify({"error": "Projekt ist noch nicht freigegeben."}), 403
    if root_project.is_completed:
        return jsonify({"error": "Das Projekt ist bereits abgeschlossen."}), 400

    # If the root project has subtasks, submissions must be on a subtask
    if not project.parent_project:
        subtask_count = Project.query.filter_by(parent_project=project.id).count()
        if subtask_count > 0:
            return jsonify(
                {
                    "error": "Dieses Projekt hat Teilaufgaben. Bitte reichen Sie Ihre Arbeit pro Aufgabe ein."
                }
            ), 400

    student_id = actor.id
    part = Participation.query.filter_by(
        student=student_id, project=project.id
    ).first()

    if part and part.is_done:
        return jsonify(
            {
                "error": "Nach der Abgabe kann nichts mehr geändert werden. Nur der/die Berufsbildner/in kann die Freigabe rückgängig machen."
            }
        ), 403

    text = (data.get("text") or "").strip() if "text" in data else (part.text if part else "")
    doc_id = (
        (int(data["document_id"]) if data.get("document_id") else None)
        if "document_id" in data
        else (part.document_id if part else None)
    )
    is_done = bool(data.get("is_done", False))
    title = (data.get("title") or "").strip() or project.title

    if is_done and not text and not doc_id:
        return jsonify(
            {
                "error": "Für die Abgabe muss mindestens ein Text oder ein Dokument eingereicht werden."
            }
        ), 400

    if part:
        part.title = title
        part.text = text
        part.document_id = doc_id
        part.is_done = is_done
        db.session.commit()
        return jsonify({"data": part.to_dict()}), 200

    part = Participation(
        supervisor=root_project.author or project.author,
        student=student_id,
        project=project.id,
        title=title,
        text=text,
        document_id=doc_id,
        is_done=is_done,
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
        return jsonify({"error": "Abgabe nicht gefunden."}), 404

    if not can_access_student(actor, part.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    project = db.session.get(Project, part.project)
    root_project = (
        db.session.get(Project, project.parent_project)
        if project and project.parent_project
        else project
    )
    if root_project and root_project.is_completed:
        return jsonify({"error": "Das Projekt ist bereits abgeschlossen."}), 400

    data = request.get_json(silent=True) or {}

    if actor.role == "ausbildner":
        # Trainers have read-only access on Durchführung, except they can undo student submission (is_done -> False)
        if set(data.keys()) <= {"is_done"} and data.get("is_done") is False:
            part.is_done = False
            db.session.commit()
            return jsonify({"data": part.to_dict()})
        return jsonify(
            {
                "error": "Vorgesetzte haben bei der Durchführung nur Leserechte und können lediglich die Freigabe/Abgabe rückgängig machen."
            }
        ), 403

    # Actor is student
    if part.student != actor.id:
        return jsonify({"error": "Keine Berechtigung."}), 403

    if part.is_done:
        return jsonify(
            {
                "error": "Nach der Abgabe kann nichts mehr geändert werden. Nur der/die Berufsbildner/in kann die Freigabe rückgängig machen."
            }
        ), 403

    if "title" in data and data["title"].strip():
        part.title = data["title"].strip()
    if "text" in data:
        part.text = (data.get("text") or "").strip()
    if "document_id" in data:
        part.document_id = int(data["document_id"]) if data.get("document_id") else None
    if "is_done" in data:
        new_done = bool(data.get("is_done"))
        if new_done and not part.text and not part.document_id:
            return jsonify(
                {
                    "error": "Für die Abgabe muss mindestens ein Text oder ein Dokument eingereicht werden."
                }
            ), 400
        part.is_done = new_done

    db.session.commit()
    return jsonify({"data": part.to_dict()})


@bp.route("/<int:part_id>", methods=["DELETE"])
@login_required
def delete_implementation(part_id):
    actor = get_current_user()
    part = db.session.get(Participation, part_id)
    if not part:
        return jsonify({"error": "Eintrag nicht gefunden."}), 404

    if actor.role != "lernender" or part.student != actor.id:
        return jsonify({"error": "Keine Berechtigung."}), 403
    if part.is_done:
        return jsonify(
            {"error": "Abgegebene Durchführungen können nicht gelöscht werden."}
        ), 403

    db.session.delete(part)
    db.session.commit()
    return jsonify({"data": {"deleted": part_id}})
