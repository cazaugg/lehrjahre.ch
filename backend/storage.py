import os
import re
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".md",
    ".txt",
    ".csv",
    ".docx",
    ".xlsx",
    ".zip",
}


def slugify_company(company_name: str) -> str:
    """Convert company name to a safe directory slug."""
    if not company_name:
        return "default-company"
    slug = company_name.strip().lower()
    slug = (
        slug.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "default-company"


def get_documents_root() -> str:
    root = os.path.realpath(current_app.config["DOCUMENTS_ROOT"])
    os.makedirs(root, mode=0o750, exist_ok=True)
    try:
        os.chmod(root, 0o750)
    except OSError:
        pass
    return root


def get_company_dir(company_name: str) -> tuple[str, str]:
    """Return (company_slug, absolute_company_dir_path) ensuring containment."""
    root = get_documents_root()
    slug = slugify_company(company_name)
    company_dir = os.path.realpath(os.path.join(root, slug))
    if not company_dir.startswith(root + os.sep):
        raise ValueError("Invalid company directory path")
    os.makedirs(company_dir, mode=0o750, exist_ok=True)
    try:
        os.chmod(company_dir, 0o750)
    except OSError:
        pass
    return slug, company_dir


def resolve_safe_path(relative_path: str) -> str:
    """Resolve a stored relative path against DOCUMENTS_ROOT and prevent traversal."""
    if not relative_path:
        raise ValueError("Empty document path")
    root = get_documents_root()
    cleaned = relative_path.lstrip("/\\")
    full_path = os.path.realpath(os.path.join(root, cleaned))
    if not full_path.startswith(root + os.sep):
        raise PermissionError("Path traversal detected")
    return full_path


def save_uploaded_file(file_storage, company_name: str) -> tuple[str, str]:
    """Save a Werkzeug FileStorage into /data/documents/<company-slug>/ and return (clean_filename, relative_path)."""
    raw_name = file_storage.filename or "document.bin"
    clean_name = secure_filename(raw_name) or "document.bin"
    ext = os.path.splitext(clean_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{ext or 'unknown'}' is not allowed.")

    slug, company_dir = get_company_dir(company_name)
    stored_name = f"{uuid.uuid4().hex[:12]}_{clean_name}"
    abs_path = os.path.realpath(os.path.join(company_dir, stored_name))
    if not abs_path.startswith(company_dir + os.sep):
        raise PermissionError("Invalid destination path")

    file_storage.save(abs_path)
    try:
        os.chmod(abs_path, 0o640)
    except OSError:
        pass
    rel_path = f"{slug}/{stored_name}"
    return clean_name, rel_path


def save_text_document(
    content: str, title: str, company_name: str, existing_rel_path: str | None = None
) -> tuple[str, str]:
    """Save or overwrite a Markdown/text document inside /data/documents/<company-slug>/."""
    safe_base = secure_filename(title) or "eintrag"
    if not safe_base.lower().endswith((".md", ".txt")):
        clean_filename = f"{safe_base}.md"
    else:
        clean_filename = safe_base

    if existing_rel_path:
        abs_path = resolve_safe_path(existing_rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content or "")
        try:
            os.chmod(abs_path, 0o640)
        except OSError:
            pass
        return clean_filename, existing_rel_path

    slug, company_dir = get_company_dir(company_name)
    stored_name = f"{uuid.uuid4().hex[:12]}_{clean_filename}"
    abs_path = os.path.realpath(os.path.join(company_dir, stored_name))
    if not abs_path.startswith(company_dir + os.sep):
        raise PermissionError("Invalid destination path")

    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content or "")
    try:
        os.chmod(abs_path, 0o640)
    except OSError:
        pass
    rel_path = f"{slug}/{stored_name}"
    return clean_filename, rel_path


def read_text_document(relative_path: str) -> str:
    """Read UTF-8 text content if the document is a text/markdown file."""
    try:
        abs_path = resolve_safe_path(relative_path)
        if not os.path.isfile(abs_path):
            return ""
        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in {".md", ".txt", ".csv"}:
            return ""
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def delete_stored_file(relative_path: str) -> None:
    """Delete a file from disk safely if it exists."""
    try:
        abs_path = resolve_safe_path(relative_path)
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except Exception:
        pass
