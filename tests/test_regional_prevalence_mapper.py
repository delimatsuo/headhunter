import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.regional_prevalence_mapper import RegionAggregate, RegionalMapperConfig, RegionalPrevalenceMapper


@pytest.mark.parametrize(
    ("location", "expected_region"),
    [
        ("São Paulo - SP", "Sudeste"),
        ("rio de janeiro (rj)", "Sudeste"),
        ("SP", "Sudeste"),
        ("MG", "Sudeste"),
        ("Fortaleza/CE", "Nordeste"),
    ],
)
def test_state_pattern_is_case_insensitive(tmp_path: Path, location: str, expected_region: str) -> None:
    config = RegionalMapperConfig(input_paths=[], output_path=tmp_path / "regional.json")
    mapper = RegionalPrevalenceMapper(config)
    posting = {config.location_field: location}
    assert mapper._region_for_posting(posting) == expected_region


def test_region_aggregate_tracks_sources() -> None:
    aggregate = RegionAggregate()
    aggregate.register("post-1", None, [], "LinkedIn")
    aggregate.register("post-2", None, [], "linkedin")
    summary = aggregate.summary()
    assert summary["sources"] == {"LINKEDIN": 2}
