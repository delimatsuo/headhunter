import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.brazilian_job_skill_extractor import load_skill_templates
from scripts.yoe_range_analyzer import run_yoe_analysis
from scripts.regional_prevalence_mapper import map_regional_prevalence
from scripts.eco_template_generator import generate_eco_templates
from scripts.orchestrate_skill_template_pipeline import (
    SkillTemplatePipelineConfig,
    SkillTemplatePipelineOrchestrator,
)
from scripts.validate_skill_templates_quality import validate_skill_templates
from scripts.load_eco_templates import _load_templates


@pytest.fixture
def job_dataset(tmp_path):
    dataset = tmp_path / "postings.jsonl"
    postings = [
        {
            "eco_occupation": "eco.br.se.frontend",
            "description": "Buscamos dev frontend com experiência obrigatória em React e TypeScript. Desejável GraphQL. Necessário 3 anos de experiência.",
            "location": "São Paulo - SP",
            "posting_id": "br-001",
            "source": "LinkedIn",
            "skills": ["React", "TypeScript", "GraphQL"],
            "salary": "R$ 12.000",
        },
        {
            "eco_occupation": "eco.br.se.frontend",
            "description": "Responsável por interfaces React, HTML, CSS. Obrigatório React. Plus Vue.js. 4 anos de experiência.",
            "location": "Rio de Janeiro - RJ",
            "posting_id": "br-002",
            "source": "Vagas",
            "skills": ["React", "HTML", "CSS", "Vue"],
            "salary": "R$ 10.000",
        },
        {
            "eco_occupation": "eco.br.se.frontend",
            "description": "Desenvolvedor front-end pleno. Precisa dominar React e testes automatizados. Experiência 3-5 anos.",
            "location": "Belo Horizonte - MG",
            "posting_id": "br-003",
            "source": "InfoJobs",
            "skills": ["React", "Testes", "Jest"],
            "salary": "R$ 11.500",
        },
        {
            "eco_occupation": "eco.br.se.frontend",
            "description": "Frontend senior com liderança, obrigatório React e TypeScript. Requer 6 anos de experiência.",
            "location": "Curitiba - PR",
            "posting_id": "br-004",
            "source": "LinkedIn",
            "skills": ["React", "TypeScript", "Leadership"],
            "salary": "R$ 13.000",
        },
        {
            "eco_occupation": "eco.br.se.frontend",
            "description": "Profissional front-end com React Native, necessário 5 anos+, diferencial GraphQL.",
            "location": "Porto Alegre - RS",
            "posting_id": "br-005",
            "source": "Gupy",
            "skills": ["React Native", "GraphQL"],
            "salary": "R$ 12.500",
        },
    ]
    with dataset.open("w", encoding="utf-8") as handle:
        for posting in postings:
            handle.write(json.dumps(posting, ensure_ascii=False) + "\n")
    return dataset


def test_skill_extractor_generates_templates(job_dataset, tmp_path):
    output = tmp_path / "skills.json"
    payload = load_skill_templates([str(job_dataset)], str(output), enable_llm=False)
    assert output.exists()
    assert payload
    occupation_payload = next(iter(payload.values()))
    assert occupation_payload["required_skills"]
    assert occupation_payload["total_observations"] >= 1


def test_pipeline_orchestrator_runs_end_to_end(job_dataset, tmp_path):
    working_dir = tmp_path / "pipeline"
    cfg = SkillTemplatePipelineConfig(
        job_posting_paths=[job_dataset],
        working_dir=working_dir,
        enable_llm=False,
        checkpoint_path=tmp_path / "checkpoint.json",
    )
    orchestrator = SkillTemplatePipelineOrchestrator(cfg)
    state = orchestrator.run()
    templates_path = working_dir / "templates" / "eco_templates.json"
    assert templates_path.exists()
    assert state["templates"]["occupations"] >= 1
    with templates_path.open("r", encoding="utf-8") as handle:
        templates = json.load(handle)
    occupation_payload = next(iter(templates.values()))
    assert occupation_payload["required_skills"]
    assert occupation_payload["prevalence_by_region"]


def test_validation_produces_report(job_dataset, tmp_path):
    working_dir = tmp_path / "validation"
    cfg = SkillTemplatePipelineConfig(
        job_posting_paths=[job_dataset],
        working_dir=working_dir,
        enable_llm=False,
    )
    SkillTemplatePipelineOrchestrator(cfg).run()
    templates_path = working_dir / "templates" / "eco_templates.json"
    report_path = tmp_path / "validation_report.json"
    result = validate_skill_templates(str(templates_path), str(report_path))
    assert report_path.exists()
    assert "completeness" in result


def test_loader_parses_template_rows(job_dataset, tmp_path):
    skills_output = tmp_path / "skills.json"
    yoe_output = tmp_path / "yoe.json"
    regional_output = tmp_path / "regional.json"
    load_skill_templates([str(job_dataset)], str(skills_output), enable_llm=False)
    run_yoe_analysis([str(job_dataset)], str(yoe_output))
    map_regional_prevalence([str(job_dataset)], str(regional_output))
    templates_path = tmp_path / "templates.json"
    evidence_path = tmp_path / "evidence.json"
    generate_eco_templates(
        str(skills_output),
        str(yoe_output),
        str(regional_output),
        str(templates_path),
        str(evidence_path),
    )
    rows = list(_load_templates(str(templates_path)))
    assert rows
    row = rows[0]
    assert row.required_skills
    assert row.metadata["prevalence_by_region"]
