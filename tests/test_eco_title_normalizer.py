import pytest

from scripts.eco_title_normalizer import EcoTitleNormalizer, normalize_title, normalize_title_ptbr


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Desenvolvedor(a) Front-end Sr", "desenvolvedor front end senior"),
        ("Engenheiro de Dados", "engenheiro de dados"),
        ("Analista Pl de Sistemas", "analista pleno de sistemas"),
        ("Dev Jr Backend", "desenvolvedor junior backend"),
        ("Arquiteto(a) de Software", "arquiteto de software"),
        ("Coordenador de TI", "coordenador de ti"),
        ("Cientista de Dados (a)", "cientista de dados"),
        ("QA/Tester", "qa tester"),
        ("Full-Stack Developer", "full stack developer"),
        ("Anal. Sr. Marketing", "analista senior marketing"),
        ("Arq. de Soluções", "arquiteto de solucoes"),
    ],
)
def test_normalizer_ptbr(raw: str, expected: str):
    assert normalize_title(raw) == expected
    assert normalize_title_ptbr(raw) == expected
    normalizer = EcoTitleNormalizer()
    assert normalizer.normalize(raw) == expected


def test_normalizer_handles_empty_inputs():
    normalizer = EcoTitleNormalizer()
    assert normalize_title("") == ""
    assert normalize_title(None) == ""  # type: ignore[arg-type]
    assert normalizer.normalize("   ") == ""
