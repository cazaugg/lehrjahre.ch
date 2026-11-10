import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, send_file
from backend.models import db, Eval, Project, Participation, Documents
from backend.auth import login_required, get_current_user, can_access_student
from backend.audit import audit
from backend.policies import (
    is_supervisor,
    is_student,
    supervised_student_ids,
    visible_project_ids_for,
    can_manage_project,
    serialize_eval,
)
from backend.validation import parse_bool, parse_int, parse_str
from backend.storage import (
    save_uploaded_file,
    delete_stored_file,
    resolve_safe_path,
)
from backend import tenants

# Nur PDF und Word-Dokumente dürfen als Auswertungsdatei beigefügt werden.
EVAL_FILE_EXTENSIONS = {".pdf", ".docx", ".doc"}


def _not_found():
    """Consistent 404 for foreign-company or otherwise inaccessible records."""
    return jsonify({"error": "Nicht gefunden."}), 404


bp = Blueprint("api_evaluation", __name__, url_prefix="/api/evaluation")


def _parse_score(score_type, score_value):
    if not isinstance(score_type, str) or score_type not in {"grade", "percent"}:
        return None, None
    if score_value is None or score_value == "":
        return score_type, None
    try:
        val = float(score_value)
    except (TypeError, ValueError):
        return score_type, None
    return score_type, val


@bp.route("", methods=["GET"])
@login_required
def list_evaluations():
    actor = get_current_user()
    student_id = request.args.get("student", type=int)
    project_id = request.args.get("project", type=int)
    participation_id = request.args.get("participation", type=int)

    visible_pids = visible_project_ids_for(actor)
    if not visible_pids:
        return jsonify({"data": []})

    query = Eval.query.filter(Eval.project.in_(visible_pids))

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
        query = query.filter(Eval.student.in_(sub_ids))

    if project_id:
        query = query.filter_by(project=project_id)
    if participation_id:
        query = query.filter_by(participation=participation_id)

    items = query.order_by(Eval.id.desc()).all()
    return jsonify({"data": [serialize_eval(item, actor) for item in items]})


@bp.route("", methods=["POST"])
@login_required
def create_evaluation():
    actor = get_current_user()
    if not is_supervisor(actor):
        return jsonify(
            {"error": "Planung und Bewertung werden durch Vorgesetzte erfasst."}
        ), 403
    data = request.get_json(silent=True) or {}

    project_id = parse_int(data.get("project"), "Projekt", min_value=1)
    target_type = parse_str(data.get("target_type"), "Zieltyp") or "goal"
    goal = parse_str(data.get("goal"), "Lernziel")
    if target_type == "goal" and not goal:
        return jsonify({"error": "Lernziel ist erforderlich."}), 400

    project = db.session.get(Project, project_id)
    if not project or not can_manage_project(actor, project):
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    if data.get("student") in (None, ""):
        return jsonify({"error": "Lernende/r muss angegeben werden."}), 400
    student_id = parse_int(data.get("student"), "Lernende/r", min_value=1)

    if not can_access_student(actor, student_id):
        return _not_found()

    participation_id = parse_int(
        data.get("participation"), "Teilnahme", allow_none=True, min_value=1
    )
    if participation_id is not None:
        participation = db.session.get(Participation, participation_id)
        if (
            not participation
            or participation.project != project.id
            or participation.student != student_id
        ):
            return jsonify({"error": "Ungültige Teilnahme."}), 400

    score_type, score_value = _parse_score(
        data.get("score_type"), data.get("score_value")
    )
    released = parse_bool(
        data.get("eval_released", data.get("is_released")), "Freigabe"
    )

    evaluation = Eval(
        project=project.id,
        participation=participation_id,
        target_type=target_type,
        goal=goal or project.title,
        student=student_id,
        # The acting supervisor is always the recorded author; never trust a
        # client-supplied user ID here.
        supervisor=actor.id,
        planning_text=parse_str(data.get("planning_text"), "Planung"),
        eval_text=parse_str(data.get("eval_text"), "Bewertung"),
        score_type=score_type,
        score_value=score_value,
        is_released=released,
        eval_released=released,
    )
    db.session.add(evaluation)
    db.session.commit()
    audit(
        "evaluation_created",
        evaluation_id=evaluation.id,
        project_id=evaluation.project,
        student_id=evaluation.student,
        released=released,
    )
    return jsonify({"data": serialize_eval(evaluation, actor)}), 201


@bp.route("/project/<int:project_id>", methods=["POST", "PUT"])
@login_required
def save_project_evaluation(project_id):
    """Save global evaluation text, per-student evaluations (project, tasks, goals), release flag, and completion status."""
    actor = get_current_user()
    if actor.role not in ("ausbildner", "admin"):
        return jsonify(
            {"error": "Auswertungen können nur von Ausbildner/innen gespeichert werden."}
        ), 403

    root_project = db.session.get(Project, project_id)
    if not root_project or root_project.parent_project is not None:
        return jsonify({"error": "Hauptprojekt nicht gefunden."}), 404
    if not can_manage_project(actor, root_project):
        return jsonify({"error": "Keine Berechtigung für dieses Projekt."}), 403

    data = request.get_json(silent=True) or {}

    student_id = parse_int(
        data.get("student"), "Lernende/r", allow_none=True, min_value=1
    )

    if "global_eval_text" in data:
        root_project.global_eval_text = parse_str(
            data.get("global_eval_text"), "Gesamtbeurteilung"
        )

    if "is_completed" in data:
        root_project.is_completed = parse_bool(
            data.get("is_completed"), "Abgeschlossen"
        )
        for child in Project.query.filter_by(parent_project=root_project.id).all():
            child.is_completed = root_project.is_completed

    is_released = False
    project_eval_record = None
    if student_id:
        if not can_access_student(actor, student_id):
            return _not_found()

        is_released = parse_bool(
            data.get("eval_released", data.get("is_released")), "Freigabe"
        )
        tasks = Project.query.filter_by(parent_project=root_project.id).all()
        task_map = {t.id: t for t in tasks}
        all_proj_ids = [root_project.id] + list(task_map.keys())

        existing_evals = Eval.query.filter(
            Eval.project.in_(all_proj_ids), Eval.student == student_id
        ).all()

        def upsert_eval(proj_id, t_type, goal_str, eval_text, s_type, s_val):
            match = None
            for ev in existing_evals:
                if (
                    ev.project == proj_id
                    and (ev.target_type or "goal") == t_type
                    and (t_type != "goal" or ev.goal == goal_str)
                ):
                    match = ev
                    break
            parsed_type, parsed_val = _parse_score(s_type, s_val)
            cleaned_text = parse_str(eval_text, "Bewertung")
            if match:
                match.goal = goal_str
                match.eval_text = cleaned_text
                match.score_type = parsed_type
                match.score_value = parsed_val
                match.is_released = is_released
                match.eval_released = is_released
                match.supervisor = actor.id
            else:
                new_ev = Eval(
                    project=proj_id,
                    target_type=t_type,
                    goal=goal_str,
                    student=student_id,
                    supervisor=actor.id,
                    eval_text=cleaned_text,
                    score_type=parsed_type,
                    score_value=parsed_val,
                    is_released=is_released,
                    eval_released=is_released,
                )
                db.session.add(new_ev)
                existing_evals.append(new_ev)
            return match or new_ev

        # 1. Overall project evaluation for student
        proj_eval = data.get("project_eval")
        if isinstance(proj_eval, dict):
            project_eval_record = upsert_eval(
                root_project.id,
                "project",
                root_project.title,
                proj_eval.get("eval_text"),
                proj_eval.get("score_type"),
                proj_eval.get("score_value"),
            )

        # 2. Per-task evaluations for student
        task_evals = data.get("task_evals")
        if isinstance(task_evals, list):
            for te in task_evals:
                if not isinstance(te, dict):
                    continue
                t_id = parse_int(
                    te.get("task_id"), "Aufgabe", allow_none=True, min_value=1
                )
                if t_id and t_id in task_map:
                    task_obj = task_map[t_id]
                    upsert_eval(
                        task_obj.id,
                        "task",
                        task_obj.title,
                        te.get("eval_text"),
                        te.get("score_type"),
                        te.get("score_value"),
                    )

        # 3. Per-goal evaluations for student
        goal_evals = data.get("goal_evals")
        if isinstance(goal_evals, list):
            for ge in goal_evals:
                if not isinstance(ge, dict):
                    continue
                g_title = parse_str(ge.get("goal"), "Lernziel")
                if g_title:
                    upsert_eval(
                        root_project.id,
                        "goal",
                        g_title,
                        ge.get("eval_text"),
                        None,
                        None,
                    )

        # Ensure all evaluations for this student on this project share the release status
        for ev in existing_evals:
            ev.is_released = is_released
            ev.eval_released = is_released

    db.session.commit()
    audit(
        "project_evaluation_saved",
        project_id=root_project.id,
        student_id=student_id,
        released=is_released,
        completed=root_project.is_completed,
    )
    return jsonify(
        {
            "data": {
                "saved": True,
                "project_id": root_project.id,
                # Needed by the frontend to attach/replace the evaluation
                # file right after saving the evaluation itself.
                "project_eval_id": (
                    project_eval_record.id if project_eval_record else None
                ),
            }
        }
    )


@bp.route("/<int:eval_id>", methods=["PUT"])
@login_required
def update_evaluation(eval_id):
    actor = get_current_user()
    if not is_supervisor(actor):
        return jsonify(
            {
                "error": "Planung und Bewertung können nur von Vorgesetzten bearbeitet werden."
            }
        ), 403

    evaluation = db.session.get(Eval, eval_id)
    if not evaluation:
        return jsonify({"error": "Bewertung nicht gefunden."}), 404

    if not can_access_student(actor, evaluation.student) or not can_manage_project(
        actor, evaluation.project_rel
    ):
        return _not_found()


    data = request.get_json(silent=True) or {}
    if "goal" in data:
        goal = parse_str(data.get("goal"), "Lernziel")
        if goal:
            evaluation.goal = goal
    if "target_type" in data:
        target_type = parse_str(data.get("target_type"), "Zieltyp")
        if target_type:
            evaluation.target_type = target_type
    if "planning_text" in data:
        evaluation.planning_text = parse_str(
            data.get("planning_text"), "Planung"
        )
    if "participation" in data:
        participation_id = parse_int(
            data.get("participation"),
            "Teilnahme",
            allow_none=True,
            min_value=1,
        )
        if participation_id is None:
            evaluation.participation = None
        else:
            participation = db.session.get(Participation, participation_id)
            if (
                not participation
                or participation.project != evaluation.project
                or participation.student != evaluation.student
            ):
                return jsonify({"error": "Ungültige Teilnahme."}), 400
            evaluation.participation = participation_id
    if "eval_text" in data:
        evaluation.eval_text = parse_str(data.get("eval_text"), "Bewertung")
    if "score_type" in data or "score_value" in data:
        s_type = data.get("score_type", evaluation.score_type)
        s_val = data.get("score_value", evaluation.score_value)
        evaluation.score_type, evaluation.score_value = _parse_score(s_type, s_val)
    if "is_released" in data or "eval_released" in data:
        released = parse_bool(
            data.get("eval_released", data.get("is_released")),
            "Freigabe",
            default=bool(evaluation.is_released),
        )
        evaluation.is_released = released
        evaluation.eval_released = released
    # The recorded supervisor is never taken from client input.
    if (
        not evaluation.supervisor
        or not evaluation.supervisor_user
        or evaluation.supervisor_user.company_id != actor.company_id
    ):
        evaluation.supervisor = actor.id

    db.session.commit()
    audit(
        "evaluation_updated",
        evaluation_id=evaluation.id,
        project_id=evaluation.project,
        student_id=evaluation.student,
        released=bool(evaluation.is_released),
    )
    return jsonify({"data": serialize_eval(evaluation, actor)})


@bp.route("/<int:eval_id>", methods=["DELETE"])
@login_required
def delete_evaluation(eval_id):
    actor = get_current_user()
    if not is_supervisor(actor):
        return jsonify(
            {"error": "Bewertungen können nur von Vorgesetzten gelöscht werden."}
        ), 403

    evaluation = db.session.get(Eval, eval_id)
    if not evaluation:
        return jsonify({"error": "Bewertung nicht gefunden."}), 404

    if not can_access_student(actor, evaluation.student) or not can_manage_project(
        actor, evaluation.project_rel
    ):
        return _not_found()


    project_id = evaluation.project
    student_id = evaluation.student
    attached_path = evaluation.document.path if evaluation.document else None
    if evaluation.document:
        db.session.delete(evaluation.document)
    db.session.delete(evaluation)
    db.session.commit()
    if attached_path:
        delete_stored_file(attached_path)
    audit(
        "evaluation_deleted",
        evaluation_id=eval_id,
        project_id=project_id,
        student_id=student_id,
    )
    return jsonify({"data": {"deleted": eval_id}})


def _eval_file_access_check(actor, evaluation):
    """Return (status_code, error_dict) or None if access is allowed.

    - Supervisors need their usual student/project permissions.
    - The evaluated student may only see the file after release (or once the
      project is completed), mirroring serialize_eval.
    """
    if is_student(actor):
        if evaluation.student != actor.id:
            return (_not_found())
        root = evaluation.project_rel
        if root is not None and root.parent_project is not None:
            root = db.session.get(Project, root.parent_project)
        released = bool(
            evaluation.eval_released or evaluation.is_released
            or (root is not None and root.is_completed)
        )
        if not released:
            return (
                jsonify(
                    {"error": "Die Auswertung wurde noch nicht freigegeben."}
                ),
                403,
            )
        return None

    if not is_supervisor(actor):
        return (_not_found())
    if not can_access_student(actor, evaluation.student) or not can_manage_project(
        actor, evaluation.project_rel
    ):
        return (_not_found())
    return None


@bp.route("/<int:eval_id>/file", methods=["GET"])
@login_required
def download_eval_file(eval_id):
    actor = get_current_user()
    evaluation = db.session.get(Eval, eval_id)
    if not evaluation or not evaluation.document:
        return jsonify({"error": "Keine Auswertungsdatei gefunden."}), 404

    denied = _eval_file_access_check(actor, evaluation)
    if denied:
        return denied

    try:
        abs_path = resolve_safe_path(evaluation.document.path)
    except (ValueError, PermissionError):
        return jsonify({"error": "Ungültiger Dateipfad."}), 400
    if not os.path.isfile(abs_path):
        return jsonify({"error": "Datei auf dem Server nicht gefunden."}), 404

    as_attachment = request.args.get("download") == "1"
    response = send_file(
        abs_path,
        as_attachment=as_attachment,
        download_name=evaluation.document.filename,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.route("/<int:eval_id>/file", methods=["POST"])
@login_required
def upload_eval_file(eval_id):
    """Attach (or replace) a PDF/Word file to a per-student project evaluation."""
    actor = get_current_user()
    if not is_supervisor(actor):
        return jsonify(
            {"error": "Auswertungsdateien können nur von Ausbildner/innen verwaltet werden."}
        ), 403

    evaluation = db.session.get(Eval, eval_id)
    if not evaluation:
        return jsonify({"error": "Bewertung nicht gefunden."}), 404
    if not can_access_student(actor, evaluation.student) or not can_manage_project(
        actor, evaluation.project_rel
    ):
        return _not_found()

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Bitte eine Datei hochladen."}), 400

    ext = os.path.splitext(uploaded_file.filename)[1].lower()
    if ext not in EVAL_FILE_EXTENSIONS:
        return jsonify(
            {"error": "Nur PDF- und Word-Dateien (.pdf, .docx, .doc) sind erlaubt."}
        ), 400

    try:
        clean_filename, rel_path = save_uploaded_file(
            uploaded_file, tenants.current_company().name
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    old_path = None
    if evaluation.document:
        old_path = evaluation.document.path
        db.session.delete(evaluation.document)

    doc = Documents(
        name=f"Projektauswertung: {evaluation.goal}",
        description=f"Beigefügte Auswertungsdatei ({ext.lstrip('.').upper()})",
        filename=clean_filename,
        path=rel_path,
        type="auswertung",
        owner=evaluation.supervisor or actor.id,
        author=actor.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )
    db.session.add(doc)
    db.session.flush()
    evaluation.document_id = doc.id
    evaluation.document = doc
    db.session.commit()
    if old_path:
        delete_stored_file(old_path)

    audit(
        "evaluation_file_uploaded",
        evaluation_id=evaluation.id,
        project_id=evaluation.project,
        student_id=evaluation.student,
        filename=clean_filename,
    )
    return jsonify({"data": serialize_eval(evaluation, actor)}), 201


@bp.route("/<int:eval_id>/file", methods=["DELETE"])
@login_required
def delete_eval_file(eval_id):
    actor = get_current_user()
    if not is_supervisor(actor):
        return jsonify(
            {"error": "Auswertungsdateien können nur von Ausbildner/innen verwaltet werden."}
        ), 403

    evaluation = db.session.get(Eval, eval_id)
    if not evaluation:
        return jsonify({"error": "Bewertung nicht gefunden."}), 404
    if not can_access_student(actor, evaluation.student) or not can_manage_project(
        actor, evaluation.project_rel
    ):
        return _not_found()

    if not evaluation.document:
        return jsonify({"error": "Keine Auswertungsdatei gefunden."}), 404

    rel_path = evaluation.document.path
    db.session.delete(evaluation.document)
    evaluation.document_id = None
    db.session.commit()
    delete_stored_file(rel_path)

    audit(
        "evaluation_file_deleted",
        evaluation_id=evaluation.id,
        project_id=evaluation.project,
        student_id=evaluation.student,
    )
    return jsonify({"data": {}})
