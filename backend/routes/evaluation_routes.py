from flask import Blueprint, request, jsonify
from backend.models import db, Eval, Project, User
from backend.auth import login_required, get_current_user, can_access_student

bp = Blueprint("api_evaluation", __name__, url_prefix="/api/evaluation")


@bp.route("", methods=["GET"])
@login_required
def list_evaluations():
    actor = get_current_user()
    student_id = request.args.get("student", type=int)
    project_id = request.args.get("project", type=int)
    participation_id = request.args.get("participation", type=int)

    if actor.role == "lernender":
        student_id = actor.id

    query = Eval.query
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
        query = query.filter(Eval.student.in_(company_student_ids))

    if project_id:
        query = query.filter_by(project=project_id)
    if participation_id:
        query = query.filter_by(participation=participation_id)

    items = query.order_by(Eval.id.desc()).all()
    return jsonify({"data": [item.to_dict() for item in items]})


@bp.route("", methods=["POST"])
@login_required
def create_evaluation():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}

    project_id = data.get("project")
    goal = (data.get("goal") or "").strip()
    if not project_id or not goal:
        return jsonify({"error": "Projekt und Lernziel sind erforderlich."}), 400

    project = db.session.get(Project, int(project_id))
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    student_id = data.get("student") if actor.role == "ausbildner" else actor.id
    if not student_id:
        return jsonify({"error": "Lernende/r muss angegeben werden."}), 400
    student_id = int(student_id)

    if not can_access_student(actor, student_id):
        return jsonify({"error": "Keine Berechtigung."}), 403

    supervisor_id = data.get("supervisor")
    if not supervisor_id and actor.role == "ausbildner":
        supervisor_id = actor.id

    evaluation = Eval(
        project=project.id,
        participation=int(data["participation"]) if data.get("participation") else None,
        goal=goal,
        student=student_id,
        supervisor=int(supervisor_id) if supervisor_id else None,
        planning_text=(data.get("planning_text") or "").strip(),
        eval_text=(data.get("eval_text") or "").strip() if actor.role == "ausbildner" else "",
    )
    db.session.add(evaluation)
    db.session.commit()
    return jsonify({"data": evaluation.to_dict()}), 201


@bp.route("/<int:eval_id>", methods=["PUT"])
@login_required
def update_evaluation(eval_id):
    actor = get_current_user()
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

    # Trainers can edit eval_text and supervisor assignment
    if actor.role == "ausbildner":
        if "eval_text" in data:
            evaluation.eval_text = (data.get("eval_text") or "").strip()
        if "supervisor" in data:
            evaluation.supervisor = int(data["supervisor"]) if data["supervisor"] else actor.id
        elif not evaluation.supervisor:
            evaluation.supervisor = actor.id

    db.session.commit()
    return jsonify({"data": evaluation.to_dict()})


@bp.route("/<int:eval_id>", methods=["DELETE"])
@login_required
def delete_evaluation(eval_id):
    actor = get_current_user()
    evaluation = db.session.get(Eval, eval_id)
    if not evaluation:
        return jsonify({"error": "Bewertung nicht gefunden."}), 404

    if not can_access_student(actor, evaluation.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    if actor.role != "ausbildner" and evaluation.eval_text:
        return jsonify(
            {"error": "Abgeschlossene Bewertungen können nur von Ausbildnern gelöscht werden."}
        ), 403

    db.session.delete(evaluation)
    db.session.commit()
    return jsonify({"data": {"deleted": eval_id}})
