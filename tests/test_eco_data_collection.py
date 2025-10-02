import json
from scrapy.http import TextResponse, Request  # type: ignore

from scripts.alias_confidence_scorer import AliasConfidenceScorer
from scripts.eco_scraper.vagas_spider import VagasSpider
from scripts.eco_scraper.catho_spider import CathoSpider
from scripts.eco_scraper.indeed_br_spider import IndeedBRSpider
from scripts.eco_scraper.infojobs_spider import InfoJobsSpider
from scripts.load_eco_aliases import read_csv_aliases


def _fake_response(url: str, body: str) -> TextResponse:
    req = Request(url=url)
    return TextResponse(url=url, request=req, body=body, encoding='utf-8')


def test_alias_confidence_basic():
    scorer = AliasConfidenceScorer()
    # identical normalized titles should yield high score
    s = scorer.score("Engenheiro de Dados", None, "engenheiro de dados", 10, 100, source="VAGAS")
    assert 0.6 <= s <= 1.0


def test_vagas_spider_parse_minimal():
    html = """
    <ul>
      <li class="lista-de-vagas__vaga">
        <h2><a href="/vaga/123">Engenheiro de Dados</a></h2>
        <span class="empr">Empresa X</span>
        <span class="vaga-local">São Paulo</span>
        <span class="data-publicacao">hoje</span>
      </li>
    </ul>
    """
    sp = VagasSpider()
    resp = _fake_response("https://www.vagas.com.br/vagas-de-ti", html)
    items = list(sp.parse(resp))
    assert len(items) == 1
    it = items[0]
    assert it["job_title"] == "Engenheiro de Dados"
    assert it["normalized_title"]
    assert it["source"] == "VAGAS"


def test_catho_spider_parse_minimal():
    html = """
    <div class="job-card">
      <h2><a href="/vaga/abc">Desenvolvedor Backend</a></h2>
      <span class="company">Acme Ltda</span>
      <span class="location">São Paulo</span>
      <time datetime="2025-09-16">2025-09-16</time>
    </div>
    """
    sp = CathoSpider()
    resp = _fake_response("https://www.catho.com.br/vagas/ti", html)
    items = list(sp.parse(resp))
    assert len(items) == 1
    it = items[0]
    assert it["job_title"] == "Desenvolvedor Backend"
    assert it["normalized_title"]
    assert it["source"] == "CATHO"


def test_indeed_br_spider_parse_minimal():
    html = """
    <div class="job_seen_beacon">
      <h2 class="jobTitle"><span>Analista de Dados</span></h2>
      <span class="companyName">Empresa Y</span>
      <div class="companyLocation">Rio de Janeiro</div>
      <a class="jcs-JobTitle" href="/viewjob?jk=123"></a>
    </div>
    """
    sp = IndeedBRSpider()
    resp = _fake_response("https://br.indeed.com/jobs?q=ti", html)
    items = list(sp.parse(resp))
    assert len(items) == 1
    it = items[0]
    assert it["job_title"] == "Analista de Dados"
    assert it["normalized_title"]
    assert it["source"] == "INDEED_BR"


def test_infojobs_spider_parse_minimal():
    html = """
    <div class="element-vaga">
      <h2><a href="/vaga/xyz">Cientista de Dados</a></h2>
      <span class="empresas"><span>Empresa Z</span></span>
      <span class="blocos-localizacao">Curitiba</span>
    </div>
    """
    sp = InfoJobsSpider()
    resp = _fake_response("https://www.infojobs.com.br/empregos.aspx?Palabra=ti", html)
    items = list(sp.parse(resp))
    assert len(items) == 1
    it = items[0]
    assert it["job_title"] == "Cientista de Dados"
    assert it["normalized_title"]
    assert it["source"] == "INFOJOBS"


def test_read_csv_aliases_empty_confidence(tmp_path):
    csv_text = """eco_id,alias,normalized_alias,confidence,source
ECO1,Dev Backend,, ,manual
ECO2,Dev Frontend,,0.9,manual
"""
    p = tmp_path / "aliases.csv"
    p.write_text(csv_text, encoding="utf-8")
    rows = list(read_csv_aliases(str(p)))
    assert len(rows) == 2
    # empty confidence should default to 0.75
    assert abs(rows[0].confidence - 0.75) < 1e-9
    assert abs(rows[1].confidence - 0.9) < 1e-9
