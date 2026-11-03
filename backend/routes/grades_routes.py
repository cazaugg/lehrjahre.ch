from datetime import date
from flask import Blueprint, request, jsonify
from backend.models import db, Grades
from backend.auth import login_required, get_current_user, can_access_student
from backend.policies import is_student, supervised_student_ids

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

    subject = (data.get("subject") or "").strip()
    title = (data.get("title") or "").strip()
    grade_val = data.get("grade")

    if not subject or not title or grade_val is None:
        return jsonify({"error": "Fach, Titel und Note sind erforderlich."}), 400

    try:
        grade_float = float(grade_val)
    except (TypeError, ValueError):
        return jsonify({"error": "Ungültiger Notenwert."}), 400

    if not (1.0 <= grade_float <= 6.0):
        return jsonify({"error": "Die Note muss zwischen 1.0 und 6.0 liegen."}), 400

    student_id = data.get("student") if actor.role == "ausbildner" else actor.id
    if not student_id:
        return jsonify({"error": "Lernende/r muss angegeben werden."}), 400
    student_id = int(student_id)

    if not can_access_student(actor, student_id):
        return jsonify({"error": "Keine Berechtigung."}), 403

    new_grade = Grades(
        student=student_id,
        subject=subject,
        date=parse_date(data.get("date")),
        grade=round(grade_float, 2),
        title=title,
        comment=(data.get("comment") or "").strip(),
    )
    db.session.add(new_grade)
    db.session.commit()
    return jsonify({"data": new_grade.to_dict()}), 201


@bp.route("/<int:grade_id>", methods=["PUT"])
@login_required
def update_grade(grade_id):
    actor = get_current_user()
    grade_obj = db.session.get(Grades, grade_id)
    if not grade_obj:
        return jsonify({"error": "Note nicht gefunden."}), 404

    if not can_access_student(actor, grade_obj.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    data = request.get_json(silent=True) or {}
    if "subject" in data and data["subject"].strip():
        grade_obj.subject = data["subject"].strip()
    if "title" in data and data["title"].strip():
        grade_obj.title = data["title"].strip()
    if "date" in data:
        grade_obj.date = parse_date(data.get("date"))
    if "comment" in data:
        grade_obj.comment = (data.get("comment") or "").strip()
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
    return jsonify({"data": grade_obj.to_dict()})


@bp.route("/<int:grade_id>", methods=["DELETE"])
@login_required
def delete_grade(grade_id):
    actor = get_current_user()
    grade_obj = db.session.get(Grades, grade_id)
    if not grade_obj:
        return jsonify({"error": "Note nicht gefunden."}), 404

    if not can_access_student(actor, grade_obj.student):
        return jsonify({"error": "Keine Berechtigung."}), 403

    db.session.delete(grade_obj)
    db.session.commit()
    return jsonify({"data": {"deleted": grade_id}})
