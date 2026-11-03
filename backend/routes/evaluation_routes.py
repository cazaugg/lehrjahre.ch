from flask import Blueprint, request, jsonify
from backend.models import db, Eval, Project, User
from backend.auth import login_required, get_current_user, can_access_student

bp = Blueprint("api_evaluation", __name__, url_prefix="/api/evaluation")


def _parse_score(score_type, score_value):
    if not score_type or score_type not in {"grade", "percent"}:
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

    items = query.order_by(Eval.id.asc()).all()
    if actor.role == "lernender":
        # Students only see released evaluations (or evaluations of completed projects)
        visible = []
        for item in items:
            proj = item.project_rel
            root = (
                db.session.get(Project, proj.parent_project)
                if proj and proj.parent_project
                else proj
            )
            if item.is_released or (root and root.is_completed):
                visible.append(item)
        items = visible

    return jsonify({"data": [item.to_dict() for item in items]})


@bp.route("", methods=["POST"])
@login_required
def create_evaluation():
    actor = get_current_user()
    if actor.role != "ausbildner":
        return jsonify(
            {"error": "Auswertungen werden durch Ausbildner/innen erfasst."}
        ), 403
    data = request.get_json(silent=True) or {}

    project_id = data.get("project")
    target_type = (data.get("target_type") or "goal").strip()
    goal = (data.get("goal") or "").strip()
    if not project_id:
        return jsonify({"error": "Projekt ist erforderlich."}), 400
    if target_type == "goal" and not goal:
        return jsonify({"error": "Lernziel ist erforderlich."}), 400

    project = db.session.get(Project, int(project_id))
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    student_id = data.get("student")
    if not student_id:
        return jsonify({"error": "Lernende/r muss angegeben werden."}), 400
    student_id = int(student_id)

    if not can_access_student(actor, student_id):
        return jsonify({"error": "Keine Berechtigung."}), 403

    supervisor_id = data.get("supervisor") or actor.id
    score_type, score_value = _parse_score(
        data.get("score_type"), data.get("score_value")
    )

    evaluation = Eval(
        project=project.id,
        participation=int(data["participation"]) if data.get("participation") else None,
        target_type=target_type,
        goal=goal or project.title,
        student=student_id,
        supervisor=int(supervisor_id) if supervisor_id else None,
        planning_text=(data.get("planning_text") or "").strip(),
        eval_text=(data.get("eval_text") or "").strip(),
        score_type=score_type,
        score_value=score_value,
        is_released=bool(data.get("is_released", False)),
    )
    db.session.add(evaluation)
    db.session.commit()
    return jsonify({"data": evaluation.to_dict()}), 201


@bp.route("/project/<int:project_id>", methods=["POST", "PUT"])
@login_required
def save_project_evaluation(project_id):
    """Save global evaluation text, per-student evaluations (project, tasks, goals), release flag, and completion status."""
    actor = get_current_user()
    if actor.role != "ausbildner":
        return jsonify(
            {"error": "Auswertungen können nur von Ausbildner/innen gespeichert werden."}
        ), 403

    root_project = db.session.get(Project, project_id)
    if not root_project or root_project.parent_project is not None:
        return jsonify({"error": "Hauptprojekt nicht gefunden."}), 404

    data = request.get_json(silent=True) or {}

    if "global_eval_text" in data:
        root_project.global_eval_text = (data.get("global_eval_text") or "").strip()

    if "is_completed" in data:
        root_project.is_completed = bool(data.get("is_completed"))
        for child in Project.query.filter_by(parent_project=root_project.id).all():
            child.is_completed = root_project.is_completed

    student_id = data.get("student")
    if student_id:
        student_id = int(student_id)
        if not can_access_student(actor, student_id):
            return jsonify({"error": "Keine Berechtigung für diese/n Lernende/n."}), 403

        is_released = bool(data.get("is_released", False))
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
            if match:
                match.goal = goal_str
                match.eval_text = (eval_text or "").strip()
                match.score_type = parsed_type
                match.score_value = parsed_val
                match.is_released = is_released
                match.supervisor = actor.id
            else:
                new_ev = Eval(
                    project=proj_id,
                    target_type=t_type,
                    goal=goal_str,
                    student=student_id,
                    supervisor=actor.id,
                    eval_text=(eval_text or "").strip(),
                    score_type=parsed_type,
                    score_value=parsed_val,
                    is_released=is_released,
                )
                db.session.add(new_ev)
                existing_evals.append(new_ev)

        # 1. Overall project evaluation for student
        proj_eval = data.get("project_eval")
        if isinstance(proj_eval, dict):
            upsert_eval(
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
                t_id = te.get("task_id")
                if t_id and int(t_id) in task_map:
                    task_obj = task_map[int(t_id)]
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
                g_title = (ge.get("goal") or "").strip()
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

    db.session.commit()
    return jsonify({"data": {"saved": True, "project_id": root_project.id}})


@bp.route("/<int:eval_id>", methods=["PUT"])
@login_required
def update_evaluation(eval_id):
    actor = get_current_user()
    evaluation = db.session.get(Eval, eval_id)
    if not evaluation:
        return jsonify({"error": "Bewertung nicht gefunden."}), 404

    if not can_access_student(actor, evaluation.student):
        return jsonify({"error": "Keine Berechtigung."}), 403
    if actor.role != "ausbildner":
        return jsonify(
            {
                "error": "Planung und Bewertung können nur von Ausbildner/innen bearbeitet werden."
            }
        ), 403

    data = request.get_json(silent=True) or {}
    if "goal" in data and data["goal"].strip():
        evaluation.goal = data["goal"].strip()
    if "target_type" in data and data["target_type"]:
        evaluation.target_type = data["target_type"]
    if "planning_text" in data:
        evaluation.planning_text = (data.get("planning_text") or "").strip()
    if "eval_text" in data:
        evaluation.eval_text = (data.get("eval_text") or "").strip()
    if "score_type" in data or "score_value" in data:
        s_type = data.get("score_type", evaluation.score_type)
        s_val = data.get("score_value", evaluation.score_value)
        evaluation.score_type, evaluation.score_value = _parse_score(s_type, s_val)
    if "is_released" in data:
        evaluation.is_released = bool(data.get("is_released"))
    if "supervisor" in data:
        evaluation.supervisor = (
            int(data["supervisor"]) if data["supervisor"] else actor.id
        )
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

    if actor.role != "ausbildner":
        return jsonify(
            {"error": "Bewertungen können nur von Ausbildnern gelöscht werden."}
        ), 403

    db.session.delete(evaluation)
    db.session.commit()
    return jsonify({"data": {"deleted": eval_id}})
