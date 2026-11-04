from flask import Blueprint, request, jsonify
from backend.models import db, Participation, Project, Documents
from backend.auth import login_required, get_current_user, can_access_student
from backend.audit import audit
from backend.policies import (
    is_supervisor,
    is_student,
    supervised_student_ids,
    visible_project_ids_for,
    can_view_project,
    can_view_document,
    can_participate_in_project,
    serialize_participation,
)
from backend.validation import parse_bool, parse_int, parse_str


def _not_found():
    """Consistent 404 for foreign-company or otherwise inaccessible records."""
    return jsonify({"error": "Nicht gefunden."}), 404


bp = Blueprint("api_implementation", __name__, url_prefix="/api/implementation")


def _validated_participation_document(actor, raw_doc_id):
    """Return (document, error). Learners may only attach their own documents."""
    if raw_doc_id in (None, ""):
        return None, None
    try:
        doc_id = int(raw_doc_id)
    except (TypeError, ValueError):
        return None, "Ungültiges Dokument."
    doc = db.session.get(Documents, doc_id)
    if not doc or doc.owner != actor.id or not can_view_document(actor, doc):
        return None, "Dokument nicht gefunden."
    return doc, None


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
            return _not_found()
        query = query.filter_by(student=actor.id)
    elif student_id:
        if not can_access_student(actor, student_id):
            return _not_found()
        query = query.filter_by(student=student_id)
    else:
        sub_ids = supervised_student_ids(actor)
        if not sub_ids:
            return jsonify({"data": []})
        query = query.filter(Participation.student.in_(sub_ids))

    if project_id:
        query = query.filter_by(project=project_id)

    items = query.order_by(Participation.id.desc()).all()
    return jsonify(
        {"data": [serialize_participation(item, actor) for item in items]}
    )


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
    project_id = parse_int(data.get("project"), "Projekt / Aufgabe", min_value=1)

    project = db.session.get(Project, project_id)
    if (
        not project
        or not can_view_project(actor, project)
        or not can_participate_in_project(actor, project)
    ):
        return jsonify({"error": "Projekt nicht gefunden oder nicht freigegeben."}), 404

    root_project = (
        db.session.get(Project, project.parent_project)
        if project.parent_project
        else project
    )
    if not root_project or not (
        root_project.is_published or root_project.planning_released
    ):
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

    text = (
        parse_str(data.get("text"), "Bericht")
        if "text" in data
        else (part.text if part else "")
    )
    if "document_id" in data:
        doc, document_error = _validated_participation_document(
            actor, data.get("document_id")
        )
        if document_error:
            return jsonify({"error": document_error}), 400
        doc_id = doc.id if doc else None
    else:
        doc_id = part.document_id if part else None
    is_done = parse_bool(data.get("is_done"), "Abgabe")
    title = parse_str(data.get("title"), "Titel") or project.title

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
        audit(
            "implementation_saved",
            participation_id=part.id,
            project_id=part.project,
            student_id=part.student,
            done=bool(part.is_done),
        )
        return jsonify({"data": serialize_participation(part, actor)}), 200

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
    audit(
        "implementation_created",
        participation_id=part.id,
        project_id=part.project,
        student_id=part.student,
        done=bool(part.is_done),
    )
    return jsonify({"data": serialize_participation(part, actor)}), 201


@bp.route("/<int:part_id>", methods=["PUT"])
@login_required
def update_implementation(part_id):
    actor = get_current_user()
    part = db.session.get(Participation, part_id)
    if not part:
        return jsonify({"error": "Abgabe nicht gefunden."}), 404

    if not can_access_student(actor, part.student) or not can_view_project(
        actor, part.project_rel
    ):
        return _not_found()

    project = db.session.get(Project, part.project)
    root_project = (
        db.session.get(Project, project.parent_project)
        if project and project.parent_project
        else project
    )
    if root_project and root_project.is_completed:
        return jsonify({"error": "Das Projekt ist bereits abgeschlossen."}), 400

    data = request.get_json(silent=True) or {}

    if is_student(actor):
        if part.student != actor.id:
            return _not_found()
        if part.is_done:
            return jsonify(
                {
                    "error": "Nach der Abgabe kann nichts mehr geändert werden. Nur der/die Berufsbildner/in kann die Freigabe rückgängig machen."
                }
            ), 403

        if "title" in data:
            title = parse_str(data.get("title"), "Titel")
            if title:
                part.title = title
        if "text" in data:
            part.text = parse_str(data.get("text"), "Bericht")
        if "document_id" in data:
            doc, document_error = _validated_participation_document(
                actor, data.get("document_id")
            )
            if document_error:
                return jsonify({"error": document_error}), 400
            part.document_id = doc.id if doc else None
        if "is_done" in data:
            new_done = parse_bool(data.get("is_done"), "Abgabe")
            if new_done and not part.text and not part.document_id:
                return jsonify(
                    {
                        "error": "Für die Abgabe muss mindestens ein Text oder ein Dokument eingereicht werden."
                    }
                ), 400
            part.is_done = new_done
    elif is_supervisor(actor):
        # Supervisors can only view the report content, but can change submission status (is_done)
        has_title_change = (
            "title" in data
            and parse_str(data.get("title"), "Titel") != (part.title or "")
        )
        has_text_change = (
            "text" in data
            and parse_str(data.get("text"), "Bericht") != (part.text or "")
        )
        new_doc_id = parse_int(
            data.get("document_id"),
            "Dokument",
            allow_none=True,
            min_value=1,
        )
        has_doc_change = "document_id" in data and new_doc_id != part.document_id
        if has_title_change or has_text_change or has_doc_change:
            return jsonify(
                {
                    "error": "Die Projektdurchführung kann von Vorgesetzten nur angezeigt werden."
                }
            ), 403
        if "is_done" in data:
            part.is_done = parse_bool(data.get("is_done"), "Abgabe")
        # The recorded supervisor is never taken from client input.
        if (
            not part.supervisor
            or not part.supervisor_user
            or part.supervisor_user.company_id != actor.company_id
        ):
            part.supervisor = actor.id
    else:
        return _not_found()

    db.session.commit()
    audit(
        "implementation_updated",
        participation_id=part.id,
        project_id=part.project,
        student_id=part.student,
        done=bool(part.is_done),
    )
    return jsonify({"data": serialize_participation(part, actor)})


@bp.route("/<int:part_id>", methods=["DELETE"])
@login_required
def delete_implementation(part_id):
    actor = get_current_user()
    part = db.session.get(Participation, part_id)
    if not part:
        return jsonify({"error": "Eintrag nicht gefunden."}), 404

    if not is_student(actor) or part.student != actor.id:
        return _not_found()
    if part.is_done:
        return jsonify(
            {"error": "Abgegebene Arbeitsberichte können nicht gelöscht werden."}
        ), 403

    project_id = part.project
    db.session.delete(part)
    db.session.commit()
    audit(
        "implementation_deleted",
        participation_id=part_id,
        project_id=project_id,
    )
    return jsonify({"data": {"deleted": part_id}})
