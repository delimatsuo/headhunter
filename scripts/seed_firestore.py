#!/usr/bin/env python3
"""Populate the Firestore emulator with multi-tenant seed data."""
from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "headhunter-local")
FIRESTORE_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
BASE_URL = f"http://{FIRESTORE_HOST}/v1/projects/{PROJECT_ID}/databases/(default)/documents"


def _firestore_value(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, Mapping):
        return {"mapValue": {"fields": {_k: _firestore_value(_v) for _k, _v in value.items()}}}
    if isinstance(value, Iterable):
        return {"arrayValue": {"values": [_firestore_value(item) for item in value]}}
    raise TypeError(f"Unsupported Firestore value type: {type(value)!r}")


def upsert_document(collection: str, doc_id: str, data: Mapping[str, Any]) -> None:
    url = f"{BASE_URL}/{collection}/{doc_id}"
    body = json.dumps({"fields": {k: _firestore_value(v) for k, v in data.items()}}).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="PATCH", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"Failed to write {collection}/{doc_id}: HTTP {response.status}")
    except urllib.error.HTTPError as error:  # pragma: no cover - emulator errors are logged
        payload = error.read().decode("utf-8") if error.fp else ""
        raise RuntimeError(f"Firestore write failed for {collection}/{doc_id}: {error} {payload}") from error


def main() -> int:
    tenants = [
        {"id": "tenant-alpha", "name": "Alpha Search Partners"},
        {"id": "tenant-beta", "name": "Beta Talent Group"},
        {"id": "tenant-gamma", "name": "Gamma Staffing Co."},
        {"id": "tenant-delta", "name": "Delta Recruiters"},
    ]

    evidence_sections = [
        "skills_analysis",
        "experience_analysis",
        "education_analysis",
        "cultural_assessment",
        "achievements",
    ]

    occupations = [
        {
            "eco_id": "ECO-2131",
            "title": "Engenheira de Software",
            "locale": "pt-BR",
            "country": "BR",
            "description": "Desenvolve e mantém plataformas de software escaláveis.",
            "aliases": ["Software Engineer", "Desenvolvedora"],
            "industries": ["Tecnologia"],
        },
        {
            "eco_id": "ECO-2422",
            "title": "Cientista de Dados",
            "locale": "pt-BR",
            "country": "BR",
            "description": "Transforma dados em insights acionáveis para o negócio.",
            "aliases": ["Data Scientist", "Especialista em Dados"],
            "industries": ["Tecnologia", "Consultoria"],
        },
        {
            "eco_id": "ECO-1120",
            "title": "Gerente de Produto",
            "locale": "pt-BR",
            "country": "BR",
            "description": "Lidera estratégias de produto e descoberta com clientes.",
            "aliases": ["Product Manager", "PM"],
            "industries": ["Tecnologia", "Serviços"],
        },
        {
            "eco_id": "ECO-1425",
            "title": "Especialista DevOps",
            "locale": "pt-BR",
            "country": "BR",
            "description": "Automatiza pipelines e opera workloads em cloud.",
            "aliases": ["DevOps Engineer", "SRE"],
            "industries": ["Tecnologia", "Telecom"],
        },
    ]

    templates = {
        "ECO-2131": {
            "summary": "Responsável por construir APIs e serviços resilientes.",
            "required_skills": ["Python", "Cloud", "PostgreSQL"],
            "preferred_skills": ["FastAPI", "Kubernetes"],
            "years_experience_min": 3,
            "years_experience_max": 8,
        },
        "ECO-2422": {
            "summary": "Desenvolve modelos estatísticos e pipelines de dados.",
            "required_skills": ["SQL", "Machine Learning", "ETL"],
            "preferred_skills": ["Airflow", "TensorFlow"],
            "years_experience_min": 4,
            "years_experience_max": 9,
        },
    }

    crosswalks = {
        "ECO-2131": {"cbo": ["2124-05"], "onet": ["15-1252.00"]},
        "ECO-2422": {"cbo": ["2131-05"], "onet": ["15-2051.00"]},
        "ECO-1120": {"cbo": ["1421-05"], "onet": ["11-2021.00"]},
    }

    aliases = {
        "ECO-2131": ["Engenheira Backend", "Software Developer"],
        "ECO-2422": ["Analista de Dados Avançados", "ML Specialist"],
        "ECO-1120": ["PM", "Gestora de Produto"],
        "ECO-1425": ["Engenheira de Confiabilidade", "Especialista SRE"],
    }

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for tenant in tenants:
        upsert_document(
            "tenants",
            tenant["id"],
            {
                "org_id": tenant["id"],
                "display_name": tenant["name"],
                "created_at": now_iso,
                "tier": "local-dev",
            },
        )

        for occupation in occupations:
            payload = dict(occupation)
            payload.update({"org_id": tenant["id"], "salary_insights": {"median": 18500, "currency": "BRL"}})
            upsert_document("eco_occupations", f"{tenant['id']}_{occupation['eco_id']}", payload)

            for alias in aliases.get(occupation["eco_id"], []):
                upsert_document(
                    "eco_aliases",
                    f"{tenant['id']}_{occupation['eco_id']}_{alias.replace(' ', '_').lower()}",
                    {
                        "eco_id": occupation["eco_id"],
                        "alias": alias,
                        "locale": occupation["locale"],
                        "org_id": tenant["id"],
                    },
                )

            template = templates.get(occupation["eco_id"])
            if template:
                upsert_document(
                    "eco_templates",
                    f"{tenant['id']}_{occupation['eco_id']}",
                    {
                        "eco_id": occupation["eco_id"],
                        "org_id": tenant["id"],
                        "locale": occupation["locale"],
                        **template,
                    },
                )

            crosswalk = crosswalks.get(occupation["eco_id"])
            if crosswalk:
                upsert_document(
                    "eco_crosswalk",
                    f"{tenant['id']}_{occupation['eco_id']}",
                    {
                        "eco_id": occupation["eco_id"],
                        "org_id": tenant["id"],
                        **crosswalk,
                    },
                )

        for index in range(1, 6):
            candidate_id = f"cand-{index:03d}"
            resume_text = (
                "Profissional com experiência em engenharia de software moderna, atuando com Python,"
                " TypeScript e arquitetura de microsserviços em ambiente cloud. Liderou iniciativas"
                " de automação CI/CD e observabilidade, com foco em entregas contínuas e qualidade."
            )

            upsert_document(
                "candidates",
                f"{tenant['id']}_{candidate_id}",
                {
                    "candidate_id": candidate_id,
                    "org_id": tenant["id"],
                    "name": f"Candidata {candidate_id.upper()}",
                    "email": f"{candidate_id}@{tenant['id']}.example.com",
                    "resume_text": resume_text,
                    "recruiter_comments": "Perfil com forte ownership, excelente colaboração e foco em produtos.",
                    "status": "pending_enrichment",
                    "uploaded_at": now_iso,
                    "metadata": {
                        "locale": "pt-BR",
                        "source": "seed-script",
                        "tenant": tenant["id"],
                        "enrichment_profile": "standard",
                        "dedupe_key": f"{tenant['id']}:{candidate_id}",
                    },
                },
            )

            analysis = {
                section: {
                    "summary": f"Resumo {section.replace('_', ' ')} para {candidate_id}.",
                    "score": round(random.uniform(0.6, 0.95), 2),
                }
                for section in evidence_sections
            }
            upsert_document(
                "candidate_evidence",
                f"{tenant['id']}_{candidate_id}",
                {
                    "org_id": tenant["id"],
                    "candidate_id": candidate_id,
                    "analysis": analysis,
                    "personal": {
                        "name": f"Candidata {candidate_id.upper()}",
                        "headline": "Profissional com histórico comprovado em tecnologia.",
                    },
                    "metadata": {
                        "generated_at": now_iso,
                        "source": "seed-script",
                        "locale": "pt-BR",
                    },
                },
            )

        enrichment_cases = [
            {
                "candidate_id": "cand-enrich-complete",
                "resume_text": "Senior full-stack developer com atuação em IA generativa e pipelines de dados.",
                "metadata": {
                    "enrichment_profile": "full",
                    "force_embedding": True,
                    "last_role": "Staff Engineer"
                },
                "recruiter_comments": "Ideal para validar enriquecimento completo com embedding",
            },
            {
                "candidate_id": "cand-enrich-missing-resume",
                "resume_text": "",
                "metadata": {
                    "enrichment_profile": "minimal",
                    "force_embedding": False,
                    "notes": "Sem currículo anexado"
                },
                "recruiter_comments": "Exercita código de fallback quando resume_text está vazio",
            },
            {
                "candidate_id": "cand-enrich-malformed",
                "resume_text": "{\"json\":\"fragment\"",  # purposely malformed for parser resilience
                "metadata": {
                    "enrichment_profile": "diagnostic",
                    "requires_cleanup": True
                },
                "recruiter_comments": "Força caminho de reparo de JSON",
            },
            {
                "candidate_id": "cand-enrich-longform",
                "resume_text": "\n".join(
                    [
                        "Experiência extensa em plataformas de alto volume, liderando equipes cross-funcionais.",
                        "Foco em observabilidade, métricas e confiabilidade de workers assíncronos.",
                        "Coordena iniciativas de dados para suportar enriquecimento em larga escala.",
                    ]
                ),
                "metadata": {
                    "enrichment_profile": "observability",
                    "target_queue": "priority",
                },
                "recruiter_comments": "Simula perfis grandes para medir percentis de latência",
            },
        ]

        for case in enrichment_cases:
            upsert_document(
                "candidates",
                f"{tenant['id']}_{case['candidate_id']}",
                {
                    "candidate_id": case["candidate_id"],
                    "org_id": tenant["id"],
                    "name": f"Perfil de Enriquecimento {case['candidate_id'].upper()}",
                    "email": f"{case['candidate_id']}@{tenant['id']}.example.com",
                    "resume_text": case["resume_text"],
                    "recruiter_comments": case["recruiter_comments"],
                    "status": "pending_enrichment",
                    "uploaded_at": now_iso,
                    "metadata": {
                        "source": "seed-script",
                        "tenant": tenant["id"],
                        **case.get("metadata", {}),
                    },
                },
            )

    print(f"Seeded Firestore emulator at {FIRESTORE_HOST} for project {PROJECT_ID}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
