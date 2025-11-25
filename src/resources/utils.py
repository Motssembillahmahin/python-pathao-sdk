from typing import Optional, Dict
import logging

from src.resources.decorators import (
    log_execution,
    measure_time,
    handle_errors,
    validate_not_empty,
    sanitize_input,
    convert_exceptions,
)
from src.resources.enums import Division, District
from src.exceptions import ValidationError

logger = logging.getLogger(__name__)


@measure_time
@sanitize_input("name", "valid_names")
def suggest_name(
    name: str, valid_names: set[str], cutoff: float = 0.6
) -> Optional[str]:
    """Return closest match to `name` from `valid_names`, or None."""
    from difflib import get_close_matches

    if not name or not valid_names:
        return None

    matches = get_close_matches(
        name.upper(), [v.upper() for v in valid_names], n=1, cutoff=cutoff
    )
    return matches[0] if matches else None


@log_execution(level="DEBUG")
@validate_not_empty("address")
def validate_address(address: str) -> bool:
    """
    Validate address format and components with comprehensive checks.

    Args:
        address: Full address string

    Returns:
        True if valid

    Raises:
        ValidationError: If address is invalid
    """
    address = address.strip()

    if not (15 <= len(address) <= 120):
        raise ValidationError(
            f"Address length must be between 15 and 120 characters (got: {len(address)})"
        )

    parts = [p.strip() for p in address.split(",") if p.strip()]

    if len(parts) < 3:
        raise ValidationError(
            "Address must contain at least area, district, and division separated by commas"
        )

    district_raw = _clean_part(parts[-2])
    division_raw = _clean_part(parts[-1])

    errors = []

    division_upper = division_raw.upper()
    if division_upper not in {d.value.upper() for d in Division}:
        suggestion = suggest_name(division_raw, {d.value for d in Division})
        if suggestion:
            errors.append(
                f"division '{division_raw}' is invalid (did you mean '{suggestion.title()}'?)"
            )
        else:
            valid_divisions = ", ".join(d.value for d in Division)
            errors.append(
                f"division '{division_raw}' is invalid. Valid: {valid_divisions}"
            )

    district_upper = district_raw.upper()
    if district_upper not in {d.value.upper() for d in District}:
        suggestion = suggest_name(district_raw, {d.value for d in District})
        if suggestion:
            errors.append(
                f"district '{district_raw}' is invalid (did you mean '{suggestion.title()}'?)"
            )
        else:
            errors.append(f"district '{district_raw}' is invalid")

    if errors:
        raise ValidationError("Invalid " + " and ".join(errors))

    return True


def _clean_part(part: str) -> str:
    """Keep only letters and spaces, strip extra spaces."""
    if not part:
        return ""
    return " ".join("".join(ch for ch in part if ch.isalpha() or ch.isspace()).split())


@convert_exceptions((IndexError, KeyError), ValidationError, "Invalid address format")
def get_district(address: str) -> str:
    """Extract district from address."""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return _clean_part(parts[-2])


@convert_exceptions((IndexError, KeyError), ValidationError, "Invalid address format")
def get_zone(address: str) -> str:
    """Extract zone/area from address."""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return parts[-3].strip()


@convert_exceptions((IndexError, KeyError), ValidationError, "Invalid address format")
def get_area(address: str) -> str:
    """Extract area (first part) from address."""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return parts[0].strip()


# ============================================================================
# CONVENIENCE FUNCTIONS WITH DECORATORS
# ============================================================================


@handle_errors(default_return=None)
@sanitize_input("address")
def parse_address(address: str) -> Optional[Dict[str, str]]:
    """
    Parse address into components with error handling.

    Args:
        address: Full address string

    Returns:
        Dictionary with address components or None on error
    """
    try:
        validate_address(address)
        return {
            "area": get_area(address),
            "zone": get_zone(address),
            "district": get_district(address),
            "full_address": address,
        }
    except Exception as e:
        logger.warning(f"Failed to parse address: {e}")
        return None
