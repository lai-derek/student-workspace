"""Separate recorded subtotals, coverage assertions and evidenced unit totals."""

from datetime import date

from .core import PlanningError, close, units


def require(condition, message):
    if not condition:
        raise PlanningError(message)


def dated(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def summarize_units(data, recorded_earned, recorded_progress):
    coverage = data.get("record_coverage", {})
    require(
        isinstance(coverage, dict)
        and not set(coverage) - {"credits", "current_coursework"},
        "record_coverage accepts only credits and current_coursework",
    )
    snapshot = data.get("audit_snapshot") or {}
    require(isinstance(snapshot, dict), "audit_snapshot must be a mapping")
    fields = ("earned_units", "in_progress_units", "minimum_degree_units")
    if any(snapshot.get(key) is not None for key in fields):
        require(
            dated(snapshot.get("as_of")) and snapshot.get("source_refs"),
            "Audit totals need dated source evidence",
        )
        for key in fields:
            if snapshot.get(key) is not None:
                units(snapshot[key], "Audit " + key)
    result = {
        "recorded_earned_units": recorded_earned,
        "recorded_in_progress_units": recorded_progress,
        "unit_coverage": {},
    }
    for domain, field, recorded, rows in [
        ("credits", "earned_units", recorded_earned, data.get("credits", [])),
        (
            "current_coursework",
            "in_progress_units",
            recorded_progress,
            data.get("current_coursework", []),
        ),
    ]:
        declared = coverage.get(domain)
        if declared is not None:
            require(
                isinstance(declared, dict)
                and declared.get("status") in {"unknown", "partial", "complete"},
                "Coverage status must be unknown, partial or complete",
            )
            if declared["status"] == "complete":
                require(
                    dated(declared.get("as_of")) and declared.get("source_refs"),
                    "Complete coverage needs dated source evidence",
                )
            elif declared.get("as_of") is not None:
                require(dated(declared["as_of"]), "Coverage date must be an ISO date")
        audited = snapshot.get(field)
        if audited is not None:
            # Explicit partial extraction may coexist with a separately evidenced audit total.
            if declared and declared["status"] in {"unknown", "partial"}:
                require(
                    recorded <= audited + 1e-8,
                    "Recorded subtotal exceeds the evidenced audit total",
                )
            else:
                close(recorded, audited, "Current " + field)
            total, basis = audited, "audit_snapshot"
            default_status = "reconciled-to-audit"
        elif declared and declared["status"] == "complete":
            total, basis = recorded, "complete-record-coverage"
            default_status = "complete"
        else:
            total, basis = None, None
            default_status = "partial" if rows else "unknown"
        result[field] = total
        result["unit_coverage"][domain] = {
            "status": declared["status"] if declared else default_status,
            "total_basis": basis,
            "as_of": snapshot.get("as_of")
            if basis == "audit_snapshot"
            else (declared or {}).get("as_of"),
            "source_refs": snapshot.get("source_refs", [])
            if basis == "audit_snapshot"
            else (declared or {}).get("source_refs", []),
        }
    minimum = snapshot.get("minimum_degree_units")
    earned, progress = result["earned_units"], result["in_progress_units"]
    result.update(
        minimum_degree_units=minimum,
        remaining_earned_units_to_minimum=max(0, minimum - earned)
        if minimum is not None and earned is not None
        else None,
        remaining_units_if_in_progress_completed=max(0, minimum - earned - progress)
        if minimum is not None and earned is not None and progress is not None
        else None,
    )
    for key in (
        "remaining_earned_units_to_minimum",
        "remaining_units_if_in_progress_completed",
    ):
        if snapshot.get(key) is not None:
            require(
                result[key] is not None,
                "Remaining-unit assertions require established totals",
            )
            close(result[key], snapshot[key], key)
    return result


def total_description(summary, domain, unit_label):
    if domain == "credits":
        field, recorded, label = (
            "earned_units",
            "recorded_earned_units",
            "Earned credit",
        )
    else:
        field, recorded, label = (
            "in_progress_units",
            "recorded_in_progress_units",
            "In-progress credit",
        )
    total = summary[field]
    value = (
        f"{total:g} {unit_label}" if total is not None else "unknown (not established)"
    )
    status = summary["unit_coverage"][domain]["status"].replace("-", " ")
    subtotal = summary[recorded]
    return f"{label}: {value}. Recorded-row subtotal: {subtotal:g} {unit_label}; coverage {status}."
