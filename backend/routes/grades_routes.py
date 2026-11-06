from datetime import date
import json
from flask import Blueprint, request, jsonify
from backend.models import db, Grades
from backend.auth import login_required, get_current_user, can_access_student
from backend.audit import audit
from backend.policies import is_student, is_supervisor, supervised_student_ids
from backend.validation import parse_int, parse_str


def _not_found():
    """Consistent 404 for foreign-company or otherwise inaccessible records."""
    return jsonify({"error": "Nicht gefunden."}), 404


def serialize_goals(goals_input) -> str:
    """Store goal strings as a JSON list (same format as Project.goals)."""
    if goals_input is None:
        return "[]"
    if isinstance(goals_input, list):
        cleaned = [str(g).strip() for g in goals_input if str(g).strip()]
        return json.dumps(cleaned, ensure_ascii=False)
    if isinstance(goals_input, str):
        lines = [line.strip() for line in goals_input.splitlines() if line.strip()]
        return json.dumps(lines, ensure_ascii=False)
    return "[]"


bp = Blueprint("api_grades", __name__, url_prefix="/api/grades")


def parse_date(val):
    if not val:
        return date.today()
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return date.today()


@bp.route("", methods=["GET"])
@login_required
def list_grades():
    actor = get_current_user()
    student_id = request.args.get("student", type=int)
    subject = request.args.get("subject")

    query = Grades.query
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
        query = query.filter(Grades.student.in_(sub_ids))

    if subject:
        query = query.filter_by(subject=subject)

    grades = query.order_by(Grades.date.desc(), Grades.id.desc()).all()
    return jsonify({"data": [g.to_dict() for g in grades]})


@bp.route("", methods=["POST"])
@login_required
def create_grade():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}

    subject = parse_str(data.get("subject"), "Fach")
    title = parse_str(data.get("title"), "Titel")
    grade_val = data.get("grade")

    if not subject or not title or grade_val is None:
        return jsonify({"error": "Fach, Titel und Note sind erforderlich."}), 400

    try:
        grade_float = float(grade_val)
    except (TypeError, ValueError):
        return jsonify({"error": "Ungültiger Notenwert."}), 400

    if not (1.0 <= grade_float <= 6.0):
        return jsonify({"error": "Die Note muss zwischen 1.0 und 6.0 liegen."}), 400

    if is_supervisor(actor):
        if data.get("student") in (None, ""):
            return jsonify({"error": "Lernende/r muss angegeben werden."}), 400
        student_id = parse_int(data.get("student"), "Lernende/r", min_value=1)
    else:
        student_id = actor.id

    if not can_access_student(actor, student_id):
        return _not_found()

    new_grade = Grades(
        student=student_id,
        subject=subject,
        date=parse_date(data.get("date")),
        grade=round(grade_float, 2),
        title=title,
        comment=parse_str(data.get("comment"), "Kommentar"),
        goals=serialize_goals(data.get("goals")),
    )
    db.session.add(new_grade)
    db.session.commit()
    audit("grade_created", grade_id=new_grade.id, student_id=student_id)
    return jsonify({"data": new_grade.to_dict()}), 201


@bp.route("/<int:grade_id>", methods=["PUT"])
@login_required
def update_grade(grade_id):
    actor = get_current_user()
    grade_obj = db.session.get(Grades, grade_id)
    if not grade_obj:
        return jsonify({"error": "Note nicht gefunden."}), 404

    if not can_access_student(actor, grade_obj.student):
        return _not_found()

    data = request.get_json(silent=True) or {}
    if "subject" in data:
        subject = parse_str(data.get("subject"), "Fach")
        if subject:
            grade_obj.subject = subject
    if "title" in data:
        title = parse_str(data.get("title"), "Titel")
        if title:
            grade_obj.title = title
    if "date" in data:
        grade_obj.date = parse_date(data.get("date"))
    if "comment" in data:
        grade_obj.comment = parse_str(data.get("comment"), "Kommentar")
    if "goals" in data:
        grade_obj.goals = serialize_goals(data.get("goals"))
    if "grade" in data:
        try:
            val = float(data["grade"])
            if not (1.0 <= val <= 6.0):
                return jsonify(
                    {"error": "Die Note muss zwischen 1.0 und 6.0 liegen."}
                ), 400
            grade_obj.grade = round(val, 2)
        except (TypeError, ValueError):
            return jsonify({"error": "Ungültiger Notenwert."}), 400

    db.session.commit()
    audit(
        "grade_updated",
        grade_id=grade_obj.id,
        student_id=grade_obj.student,
    )
    return jsonify({"data": grade_obj.to_dict()})


@bp.route("/<int:grade_id>", methods=["DELETE"])
@login_required
def delete_grade(grade_id):
    actor = get_current_user()
    grade_obj = db.session.get(Grades, grade_id)
    if not grade_obj:
        return jsonify({"error": "Note nicht gefunden."}), 404

    if not can_access_student(actor, grade_obj.student):
        return _not_found()

    student_id = grade_obj.student
    db.session.delete(grade_obj)
    db.session.commit()
    audit("grade_deleted", grade_id=grade_id, student_id=student_id)
    return jsonify({"data": {"deleted": grade_id}})
