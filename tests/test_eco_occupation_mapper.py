from pathlib import Path

import pytest

from scripts.eco_occupation_mapper import EcoOccupationMapper, OccupationMapperConfig


@pytest.fixture
def mapper() -> EcoOccupationMapper:
    config = OccupationMapperConfig(clusters_path=Path("dummy.json"), category="ENGINEERING")
    return EcoOccupationMapper(config)


def test_build_occupation_id_sanitizes_cluster_keys(mapper: EcoOccupationMapper) -> None:
    assert mapper._build_occupation_id("frontend:101") == "ECO.BR.SE.ENGINEERING.101"
    assert mapper._build_occupation_id("default:3") == "ECO.BR.SE.ENGINEERING.3"
    assert mapper._build_occupation_id("QA Lead!") == "ECO.BR.SE.ENGINEERING.QA_Lead"


def test_find_progressions_matches_examples(mapper: EcoOccupationMapper) -> None:
    cluster_info = {
        "representative": {"text": "Engenheiro de Dados"},
        "titles": [
            {"text": "Engenheiro de Dados Pleno"},
            {"text": "Cientista de Dados"},
        ],
    }
    progression = {
        "progressions": [
            {
                "from_level": "pleno",
                "to_level": "senior",
                "examples": [{"text": "Engenheiro de Dados"}],
            },
            {
                "from_level": "junior",
                "to_level": "pleno",
                "examples": ["Engenheiro de Dados Pleno"],
            },
            {
                "from_level": "analista",
                "to_level": "coordenador",
                "examples": [{"text": "Outro Título"}],
            },
        ]
    }
    matches = mapper._find_progressions_for_cluster(cluster_info, progression)
    assert len(matches) == 2
    assert all(match["to_level"] in {"senior", "pleno"} for match in matches)
