import json
from datetime import date
from flask import Blueprint, request, jsonify
from backend.models import db, Project
from backend.auth import login_required, role_required, get_current_user
from backend.policies import (
    visible_project_ids_for,
    can_view_project,
    can_manage_project,
)

bp = Blueprint("api_project", __name__, url_prefix="/api/project")


def parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def serialize_goals(goals_input) -> str:
    if goals_input is None:
        return "[]"
    if isinstance(goals_input, list):
        cleaned = [str(g).strip() for g in goals_input if str(g).strip()]
        return json.dumps(cleaned, ensure_ascii=False)
    if isinstance(goals_input, str):
        lines = [line.strip() for line in goals_input.splitlines() if line.strip()]
        return json.dumps(lines, ensure_ascii=False)
    return "[]"


@bp.route("", methods=["GET"])
@login_required
def list_projects():
    actor = get_current_user()
    visible_ids = visible_project_ids_for(actor)
    if not visible_ids:
        return jsonify({"data": []})
    projects = (
        Project.query.filter(Project.id.in_(visible_ids))
        .order_by(Project.start_date.desc().nullslast(), Project.id.desc())
        .all()
    )
    return jsonify({"data": [p.to_dict() for p in projects]})


@bp.route("/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    actor = get_current_user()
    project = db.session.get(Project, project_id)
    if not project or not can_view_project(actor, project):
        return jsonify({"error": "Projekt nicht gefunden."}), 404
    return jsonify({"data": project.to_dict()})


@bp.route("", methods=["POST"])
@role_required("ausbildner")
def create_project():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Projekttitel ist erforderlich."}), 400

    parent_id = data.get("parent_project")
    if parent_id:
        parent = db.session.get(Project, int(parent_id))
        if not parent or not can_manage_project(actor, parent):
            return jsonify({"error": "Übergeordnetes Projekt nicht gefunden."}), 400
        parent_id = parent.id
    else:
        parent_id = None

    project = Project(
        parent_project=parent_id,
        title=title,
        description=(data.get("description") or "").strip(),
        author=actor.id,
        goals=serialize_goals(data.get("goals")),
        start_date=parse_date(data.get("start_date")),
        due_date=parse_date(data.get("due_date")),
        planning_released=bool(data.get("planning_released", False)),
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({"data": project.to_dict()}), 201


@bp.route("/<int:project_id>", methods=["PUT"])
@role_required("ausbildner")
def update_project(project_id):
    actor = get_current_user()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404
    if not can_manage_project(actor, project):
        return jsonify({"error": "Keine Berechtigung für dieses Projekt."}), 403

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"].strip():
        project.title = data["title"].strip()
    if "description" in data:
        project.description = (data.get("description") or "").strip()
    if "parent_project" in data:
        parent_id = data.get("parent_project")
        if parent_id and int(parent_id) != project.id:
            parent = db.session.get(Project, int(parent_id))
            if not parent or not can_manage_project(actor, parent):
                return jsonify({"error": "Ungültiges übergeordnetes Projekt."}), 400
            project.parent_project = parent.id
        else:
            project.parent_project = None
    if "goals" in data:
        project.goals = serialize_goals(data.get("goals"))
    if "start_date" in data:
        project.start_date = parse_date(data.get("start_date"))
    if "due_date" in data:
        project.due_date = parse_date(data.get("due_date"))
    if "planning_released" in data:
        project.planning_released = bool(data.get("planning_released"))

    db.session.commit()
    return jsonify({"data": project.to_dict()})


@bp.route("/<int:project_id>", methods=["DELETE"])
@role_required("ausbildner")
def delete_project(project_id):
    actor = get_current_user()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404
    if not can_manage_project(actor, project):
        return jsonify({"error": "Keine Berechtigung für dieses Projekt."}), 403

    db.session.delete(project)
    db.session.commit()
    return jsonify({"data": {"deleted": project_id}})
