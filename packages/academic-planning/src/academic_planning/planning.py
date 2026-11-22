"""Conditional recognition and scoped research; no personal course defaults."""

from datetime import date

from .core import PlanningError, units


def require(condition, message):
    if not condition:
        raise PlanningError(message)


def dated(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_planning_records(data, abroad):
    require(
        "breadth_credit_ruling" not in data,
        "Obsolete breadth_credit_ruling: consolidate into recognition_options",
    )
    credits = {r["id"]: r for r in data.get("credits", [])}
    requirements = {r["id"] for r in data.get("requirements", [])}
    seen = set()
    for option in data.get("recognition_options", []):
        require(
            isinstance(option.get("id"), str)
            and option["id"]
            and option["id"] not in seen,
            "Duplicate or missing recognition ID",
        )
        seen.add(option["id"])
        require(
            isinstance(option.get("area"), str) and option["area"].strip(),
            "Recognition needs an area",
        )
        for key, known in [("credit_ids", credits), ("requirement_ids", requirements)]:
            values = option.get(key, [])
            require(
                isinstance(values, list)
                and values
                and all(isinstance(v, str) for v in values)
                and len(set(values)) == len(values)
                and all(v in known for v in values),
                f"Unknown or duplicate recognition {key}",
            )
        require(
            option.get("eligibility") in {"approved", "pending", "rejected"},
            "Unknown recognition eligibility",
        )
        require(
            option["eligibility"] != "approved" or option.get("approval_source"),
            "Approved recognition requires approval evidence",
        )
        require(
            all(credits[key]["awarded_units"] > 0 for key in option["credit_ids"]),
            "Recognition requires positive existing awards",
        )
        minimum = option.get("minimum_courses")
        require(
            type(minimum) is int
            and minimum > 0
            and minimum == len(option["requirement_ids"]),
            "Recognition course minimum must match its requirement slots",
        )
        units(option.get("minimum_units"), "Recognition minimum", positive=True)
        for key, evidence in [
            ("declaration_status", "declaration_source"),
            ("dars_application", "dars_source"),
        ]:
            require(
                option.get(key) in {"unconfirmed", "confirmed"},
                f"Unknown recognition {key}",
            )
            require(
                option[key] != "confirmed" or option.get(evidence),
                f"Confirmed {key} requires its own evidence",
            )
    wanted = abroad.get("useful_requirement_ids", [])
    require(
        isinstance(wanted, list)
        and all(isinstance(v, str) for v in wanted)
        and len(set(wanted)) == len(wanted)
        and all(v in requirements for v in wanted),
        "Unknown or duplicate useful requirement ID",
    )
    for owner in (data, abroad):
        seen = set()
        for row in owner.get("research_updates", []):
            require(
                isinstance(row.get("id"), str) and row["id"] and row["id"] not in seen,
                "Duplicate or missing research update ID",
            )
            seen.add(row["id"])
            require(
                row.get("source_refs")
                and row.get("summary")
                and row.get("topic")
                and dated(row.get("as_of")),
                "Research updates need dated evidence, topic and summary",
            )
            for old in row.get("supersedes", []):
                require(
                    isinstance(old.get("scope"), str)
                    and old["scope"].strip()
                    and old.get("source_refs"),
                    "Supersession requires an explicit scope and prior evidence",
                )


def recognition_options(academic):
    credits = {r["id"]: r for r in academic.get("credits", [])}
    result = []
    for option in academic.get("recognition_options", []):
        awards = (
            [credits[key] for key in option["credit_ids"]]
            if option["eligibility"] == "approved"
            else []
        )
        total = sum(r["awarded_units"] for r in awards)
        result.append(
            dict(
                option,
                approved_existing_courses=len(awards),
                existing_awarded_units=total,
                new_courses_remaining=max(0, option["minimum_courses"] - len(awards)),
                new_units_remaining=max(0, option["minimum_units"] - total),
            )
        )
    return result


def recognition_summary(option):
    return (
        f"If {option['area']} is chosen: existing-credit eligibility {option['eligibility']}; "
        f"{option['approved_existing_courses']} existing courses / {option['existing_awarded_units']:g} awarded units approved. "
        f"New coursework still needed: {option['new_courses_remaining']} course(s), at least {option['new_units_remaining']:g} units "
        f"to meet {option['minimum_courses']} courses / {option['minimum_units']:g} units. "
        f"Declaration {option['declaration_status']}; DARS application {option['dars_application']}. "
        "Recognition adds no earned units and does not select an area or approve host courses."
    )


def useful_requirements(academic, abroad):
    wanted = set(abroad.get("useful_requirement_ids", []))
    return [dict(r) for r in academic.get("requirements", []) if r["id"] in wanted]


def research_lines(owner):
    """Keep every finding and its claim scope visible, even with a shared source."""
    result = []
    for row in owner.get("research_updates", []):
        result.append(f"{row['as_of']} / {row['topic']}: {row['summary']}")
        result.append("Evidence: " + "; ".join(row["source_refs"]))
        for old in row.get("supersedes", []):
            result.append(
                "Supersedes only: "
                + old["scope"]
                + "; prior evidence: "
                + "; ".join(old["source_refs"])
            )
    return result
