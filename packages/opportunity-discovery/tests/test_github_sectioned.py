from pathlib import Path

import pytest

from opportunity_discovery.adapters.base import run_source
from opportunity_discovery.registry import load_sources
from tests.helpers import load_fixture, source

URL = "https://raw.example.org/early.md"


def spec(**config):
    return source(
        source_id="gh-early",
        adapter="githublist",
        official_source=False,
        organization="Community aggregator",
        endpoint_config={"url": URL, "format": "sectioned_table", **config},
    )


def test_sectioned_tables_keep_links_eligibility_and_independent_headers(mock_fetcher):
    mock_fetcher.add(URL, 200, load_fixture("sectioned_board.md"))
    result = run_source(spec(expected_tables=3, min_results=1), mock_fetcher)
    assert result.ok and len(result.records) == 4
    internship, firmware, research, scholarship = result.records
    assert internship.canonical_url == "https://acme.example.org/intern"
    assert internship.organization == firmware.organization == "Acme Circuits"
    assert firmware.title == "Firmware Intern"
    assert research.organization == "Example University"
    assert research.title == "Summer Research" and research.location_text == "Austin, TX"
    assert scholarship.title == "Early Scholars"
    assert "Sophomores; GPA 3.0; resident of CA" in scholarship.requirements_text
    assert "citizenship required" in internship.requirements_text
    assert "January 15, 2027" in scholarship.requirements_text
    assert scholarship.deadline is None  # ambiguous/natural date retained as source language
    assert all(record.application_state == "unknown" for record in result.records)
    assert all(record.posted_date is None for record in result.records)
    assert all(record.evidence == "source-stated" for record in result.records)


def test_sectioned_linked_names_keep_year_notes_and_skip_only_unlinked_rows(mock_fetcher):
    mock_fetcher.add(
        URL,
        200,
        "| Name | Year | Note |\n| --- | --- | --- |\n"
        "| [Acme Prep](https://acme.example.org/prep) | Freshman | Paid; CS or EE |\n"
        "| Unannounced program | Sophomore | No application URL |\n",
    )
    result = run_source(
        spec(columns={"title": "Name", "canonical_url": "Name"}, allow_unlinked_rows=True),
        mock_fetcher,
    )
    assert result.ok and len(result.records) == 1
    assert result.records[0].title == "Acme Prep"
    assert "Freshman" in result.records[0].requirements_text
    assert "Paid; CS or EE" in result.records[0].requirements_text


@pytest.mark.parametrize(
    "body",
    [
        "<html>Upstream error</html>",
        "| Role | Application |\n| --- | --- |\n| Intern | |\n",
        "| Role | Application |\n| --- | --- |\n| Intern | https://acme.example.org/apply | extra |\n",
        "| Changed | Application |\n| --- | --- |\n| Intern | https://acme.example.org/apply |\n",
        # A later broken table must discard earlier valid records.
        "| Role | Application |\n| --- | --- |\n| Intern | https://acme.example.org/apply |\n\n"
        "| Program | Application |\n| --- | --- |\n| Prep | missing |\n",
    ],
)
def test_sectioned_malformed_or_partial_tables_fail_without_records(mock_fetcher, body):
    mock_fetcher.add(URL, 200, body)
    result = run_source(spec(), mock_fetcher)
    assert not result.ok and not result.empty_ok and not result.records
    assert result.state == "format-changed"


@pytest.mark.parametrize("config", [{"expected_tables": 4}, {"min_results": 5}, {"max_results": 3}])
def test_sectioned_coverage_canaries_discard_partial_results(mock_fetcher, config):
    mock_fetcher.add(URL, 200, load_fixture("sectioned_board.md"))
    result = run_source(spec(**config), mock_fetcher)
    assert not result.ok and not result.records and result.state == "coverage-warning"


def test_sectioned_valid_empty_requires_recognized_header(mock_fetcher):
    mock_fetcher.add(URL, 200, "| Role | Application |\n| --- | --- |\n")
    result = run_source(spec(expected_tables=1), mock_fetcher)
    assert result.ok and result.empty_ok and not result.records


def test_sectioned_bounds_text_but_preserves_eligibility(mock_fetcher):
    title = "Research " + "project " * 100
    mock_fetcher.add(
        URL,
        200,
        "| Program | Eligibility | Application |\n| --- | --- | --- |\n"
        f"| {title} | Freshman; EE only | https://acme.example.org/research |\n",
    )
    result = run_source(spec(), mock_fetcher, excerpt_chars=100)
    assert result.ok and len(result.records[0].title) <= 240
    assert len(result.records[0].description_excerpt) <= 100
    assert len(result.records[0].requirements_text) <= 2400
    assert "Freshman; EE only" in result.records[0].requirements_text


def test_sectioned_transport_failure_is_not_empty_success(mock_fetcher):
    mock_fetcher.add(URL, 503, "unavailable")
    result = run_source(spec(), mock_fetcher)
    assert not result.ok and not result.empty_ok and not result.records


def test_sectioned_cached_304_is_reparsed(mock_fetcher):
    mock_fetcher.add(URL, 304, load_fixture("sectioned_board.md"))
    result = run_source(spec(expected_tables=3), mock_fetcher)
    assert result.ok and len(result.records) == 4


def test_underclassmen_registry_enables_validated_feed_and_quarantines_zapply():
    sources, errors = load_sources(Path(__file__).resolve().parents[1] / "config/sources.toml")
    assert not errors
    by_id = {item.source_id: item for item in sources}
    active = by_id["agg-underclassmen-opportunities"]
    assert active.enabled and active.validation_status == "validated"
    assert not active.official_source and active.endpoint_config["expected_tables"] == 9
    reference = by_id["agg-zapply-underclassmen"]
    assert not reference.enabled and reference.validation_status == "quarantined"
    assert "third-party aggregators" in reference.quarantine_reason


def test_program_and_scholarship_tables_state_the_job_type(mock_fetcher):
    from opportunity_discovery import constants as c
    from opportunity_discovery.routing import normalize_routing_fields, route_profiles

    mock_fetcher.add(URL, 200, load_fixture("sectioned_board.md"))
    result = run_source(spec(expected_tables=3, min_results=1), mock_fetcher)
    internship, firmware, research, scholarship = result.records
    assert internship.engagement_type is None and firmware.engagement_type is None  # "Role" table
    assert research.engagement_type == scholarship.engagement_type == "program"
    for record in (research, scholarship):
        fields = normalize_routing_fields(record)
        assert fields["engagement_type"] == c.ENGAGEMENT_PROGRAM
        assert route_profiles(fields)[c.PROFILE_STUDENT].state == c.ROUTE_INCLUDED
