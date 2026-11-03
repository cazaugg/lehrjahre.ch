from flask import Blueprint, request, jsonify
from backend.models import db, Eval, Project
from backend.auth import login_required, get_current_user, can_access_student
from backend.policies import (
    is_supervisor,
    is_student,
    supervised_student_ids,
    visible_project_ids_for,
    can_manage_project,
    serialize_eval,
)

bp = Blueprint("api_evaluation", __name__, url_prefix="/api/evaluation")


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

    project_id = data.get("project")
    goal = (data.get("goal") or "").strip()
    if not project_id or not goal:
        return jsonify({"error": "Projekt und Lernziel sind erforderlich."}), 400

    project = db.session.get(Project, int(project_id))
    if not project or not can_manage_project(actor, project):
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    student_id = data.get("student")
    if not student_id:
        return jsonify({"error": "Lernende/r muss angegeben werden."}), 400
    student_id = int(student_id)

    if not can_access_student(actor, student_id):
        return jsonify({"error": "Keine Berechtigung."}), 403

    supervisor_id = data.get("supervisor") or actor.id

    evaluation = Eval(
        project=project.id,
        participation=int(data["participation"]) if data.get("participation") else None,
        goal=goal,
        student=student_id,
        supervisor=int(supervisor_id) if supervisor_id else None,
        planning_text=(data.get("planning_text") or "").strip(),
        eval_text=(data.get("eval_text") or "").strip(),
        eval_released=bool(data.get("eval_released", False)),
    )
    db.session.add(evaluation)
    db.session.commit()
    return jsonify({"data": serialize_eval(evaluation, actor)}), 201


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

    if not can_access_student(actor, evaluation.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    data = request.get_json(silent=True) or {}
    if "goal" in data and data["goal"].strip():
        evaluation.goal = data["goal"].strip()
    if "planning_text" in data:
        evaluation.planning_text = (data.get("planning_text") or "").strip()
    if "participation" in data:
        evaluation.participation = (
            int(data["participation"]) if data.get("participation") else None
        )
    if "eval_text" in data:
        evaluation.eval_text = (data.get("eval_text") or "").strip()
    if "eval_released" in data:
        evaluation.eval_released = bool(data.get("eval_released"))
    if "supervisor" in data:
        evaluation.supervisor = (
            int(data["supervisor"]) if data["supervisor"] else actor.id
        )
    elif not evaluation.supervisor:
        evaluation.supervisor = actor.id

    db.session.commit()
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

    if not can_access_student(actor, evaluation.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    db.session.delete(evaluation)
    db.session.commit()
    return jsonify({"data": {"deleted": eval_id}})
