import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, send_file
from backend.models import db, Documents, User
from backend.auth import login_required, get_current_user, can_access_student
from backend.storage import (
    save_uploaded_file,
    save_text_document,
    read_text_document,
    resolve_safe_path,
    delete_stored_file,
)

bp = Blueprint("api_documents", __name__, url_prefix="/api/documents")

VALID_TYPES = {
    "zeugnis",
    "ausbildungsgespraech",
    "kursnachweis",
    "lernjournal",
    "wissen",
    "vertrag",
    "bewerbung",
    "profilbild",
    "projekt",
    "sonstiges",
}


def can_access_document(actor: User, doc: Documents) -> bool:
    if doc.owner == actor.id or doc.author == actor.id:
        return True
    owner = db.session.get(User, doc.owner)
    if not owner or owner.company != actor.company:
        return False
    # Shared templates, knowledge pages, or trainer project documents in the same company
    if doc.is_template or doc.type in {"wissen", "profilbild"}:
        return True
    if doc.type == "projekt" and owner.role == "ausbildner":
        return True
    return can_access_student(actor, doc.owner)


@bp.route("", methods=["GET"])
@login_required
def list_documents():
    actor = get_current_user()
    doc_type = request.args.get("type")
    owner_id = request.args.get("owner", type=int)
    is_template = request.args.get("is_template")
    include_content = request.args.get("include_content") == "true"

    company_user_ids = [
        u.id for u in User.query.filter_by(company=actor.company).all()
    ]
    query = Documents.query.filter(Documents.owner.in_(company_user_ids))

    if doc_type:
        query = query.filter_by(type=doc_type)

    if is_template is not None:
        query = query.filter_by(is_template=(is_template.lower() == "true"))
    else:
        if actor.role == "lernender" and doc_type not in {"wissen", "profilbild"}:
            # Students see their own documents plus templates of that type
            query = query.filter(
                (Documents.owner == actor.id) | (Documents.is_template.is_(True))
            )
        elif owner_id:
            if not can_access_student(actor, owner_id):
                return jsonify({"error": "Keine Berechtigung."}), 403
            query = query.filter(
                (Documents.owner == owner_id) | (Documents.is_template.is_(True))
            )

    docs = query.order_by(Documents.updated_date.desc(), Documents.id.desc()).all()
    result = []
    for d in docs:
        item = d.to_dict()
        if include_content or d.type in {"lernjournal", "wissen", "ausbildungsgespraech"}:
            item["content"] = read_text_document(d.path)
        result.append(item)

    return jsonify({"data": result})


@bp.route("/<int:doc_id>", methods=["GET"])
@login_required
def get_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_access_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    data = doc.to_dict()
    data["content"] = read_text_document(doc.path)
    return jsonify({"data": data})


@bp.route("/<int:doc_id>/file", methods=["GET"])
@login_required
def download_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_access_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    try:
        abs_path = resolve_safe_path(doc.path)
    except (ValueError, PermissionError):
        return jsonify({"error": "Ungültiger Dateipfad."}), 400

    if not os.path.isfile(abs_path):
        return jsonify({"error": "Datei auf dem Server nicht gefunden."}), 404

    as_attachment = request.args.get("download") == "1"
    return send_file(
        abs_path,
        as_attachment=as_attachment,
        download_name=doc.filename,
    )


@bp.route("", methods=["POST"])
@login_required
def create_document():
    actor = get_current_user()

    # Support both multipart/form-data (file upload) and JSON (text/markdown document)
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        uploaded_file = request.files.get("file")
        name = (form.get("name") or "").strip()
        description = (form.get("description") or "").strip()
        doc_type = (form.get("type") or "sonstiges").strip().lower()
        owner_id = form.get("owner", type=int) or actor.id
        is_template = form.get("is_template", "false").lower() == "true"
        is_done = form.get("is_done", "false").lower() == "true"
        text_content = form.get("content")
    else:
        data = request.get_json(silent=True) or {}
        uploaded_file = None
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        doc_type = (data.get("type") or "sonstiges").strip().lower()
        owner_id = int(data.get("owner") or actor.id)
        is_template = bool(data.get("is_template", False))
        is_done = bool(data.get("is_done", False))
        text_content = data.get("content")

    if doc_type not in VALID_TYPES:
        doc_type = "sonstiges"

    if actor.role == "lernender":
        owner_id = actor.id
        is_template = False
    elif not can_access_student(actor, owner_id):
        return jsonify({"error": "Keine Berechtigung für diesen Eigentümer."}), 403

    owner_user = db.session.get(User, owner_id)
    if not owner_user:
        return jsonify({"error": "Eigentümer nicht gefunden."}), 404

    if uploaded_file and uploaded_file.filename:
        if not name:
            name = uploaded_file.filename
        try:
            clean_filename, rel_path = save_uploaded_file(
                uploaded_file, owner_user.company
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    elif text_content is not None:
        if not name:
            return jsonify({"error": "Dokumentname ist erforderlich."}), 400
        clean_filename, rel_path = save_text_document(
            text_content, name, owner_user.company
        )
    else:
        return jsonify(
            {"error": "Bitte eine Datei hochladen oder Textinhalt angeben."}
        ), 400

    doc = Documents(
        name=name,
        description=description,
        filename=clean_filename,
        path=rel_path,
        type=doc_type,
        owner=owner_user.id,
        author=actor.id,
        is_template=is_template,
        updated_date=datetime.now(timezone.utc),
        is_done=is_done,
    )
    db.session.add(doc)
    db.session.commit()

    res = doc.to_dict()
    if text_content is not None:
        res["content"] = text_content
    return jsonify({"data": res}), 201


@bp.route("/<int:doc_id>", methods=["PUT"])
@login_required
def update_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_access_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    if actor.role == "lernender" and doc.owner != actor.id:
        return jsonify({"error": "Keine Berechtigung."}), 403

    data = request.get_json(silent=True) or {}
    if "name" in data and data["name"].strip():
        doc.name = data["name"].strip()
    if "description" in data:
        doc.description = (data.get("description") or "").strip()
    if "is_done" in data:
        doc.is_done = bool(data.get("is_done"))
    if actor.role == "ausbildner" and "is_template" in data:
        doc.is_template = bool(data.get("is_template"))

    if "content" in data and data["content"] is not None:
        owner_user = db.session.get(User, doc.owner) or actor
        _, rel_path = save_text_document(
            data["content"], doc.name, owner_user.company, existing_rel_path=doc.path
        )
        doc.path = rel_path

    doc.updated_date = datetime.now(timezone.utc)
    db.session.commit()

    res = doc.to_dict()
    res["content"] = read_text_document(doc.path)
    return jsonify({"data": res})


@bp.route("/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    actor = get_current_user()
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_access_document(actor, doc):
        return jsonify({"error": "Dokument nicht gefunden."}), 404

    if actor.role == "lernender" and doc.owner != actor.id:
        return jsonify({"error": "Keine Berechtigung zum Löschen."}), 403

    rel_path = doc.path
    db.session.delete(doc)
    db.session.commit()
    delete_stored_file(rel_path)

    return jsonify({"data": {"deleted": doc_id}})
