class ValidationError(ValueError):
    """Raised when a request value has an invalid shape or type."""


def parse_int(value, field="ID", allow_none=False, min_value=None):
    """Parse an integer request value and raise ValidationError on bad input."""
    if value in (None, ""):
        if allow_none:
            return None
        raise ValidationError(f"{field} ist erforderlich.")
    if isinstance(value, bool):
        raise ValidationError(f"Ungültiger Wert für {field}.")
    if isinstance(value, float) and not value.is_integer():
        raise ValidationError(f"Ungültiger Wert für {field}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Ungültiger Wert für {field}.") from exc
    if min_value is not None and parsed < min_value:
        raise ValidationError(f"Ungültiger Wert für {field}.")
    return parsed


def parse_bool(value, field="Wert", default=False):
    """Parse a JSON boolean without treating the string "false" as truthy."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0", ""}:
            return False
    raise ValidationError(f"Ungültiger Wert für {field}.")


def parse_str(value, field="Wert", default="", strip=True, allow_none=False):
    """Parse a string request value and raise ValidationError for other types."""
    if value is None:
        if allow_none:
            return None
        return default
    if not isinstance(value, str):
        raise ValidationError(f"Ungültiger Wert für {field}.")
    return value.strip() if strip else value
