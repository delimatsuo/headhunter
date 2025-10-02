import json
from datetime import datetime
from pathlib import Path

from scripts.alias_confidence_scorer import AliasConfidenceScorer
from scripts.eco_clustering_validator import ClusteringValidator, ClusteringValidatorConfig
from scripts.eco_template_accuracy_validator import TemplateAccuracyValidator, TemplateAccuracyValidatorConfig
from scripts.orchestrate_eco_quality_assurance import ECOQualityOrchestrator, OrchestratorConfig


class TestValidationQueue:
    def test_populate_queue_without_database(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(output_dir=tmp_path)
        orchestrator = ECOQualityOrchestrator(config)
        result = orchestrator.populateValidationQueue()
        assert result["count"] >= 1
        report_path = tmp_path / "validation_queue_batch.json"
        assert report_path.exists()


class TestConfidenceScoring:
    def test_score_with_evidence_improves_base_score(self) -> None:
        scorer = AliasConfidenceScorer()
        evidence = [
            {"source": "linkedIn", "confidence": 0.9, "weight": 2, "postings": 5},
            {"source": "recruiter_feedback", "confidence": 0.95, "weight": 1, "postings": 3},
        ]
        breakdown = scorer.scoreWithEvidence(
            alias="engenheiro de dados senior",
            canonical_norm="engenheiro de dados",
            evidence_sources=evidence,
            posting_volume=12,
            last_seen_date=datetime.utcnow().isoformat(),
            total_postings=50,
            alias_variants=[("engenheira de dados senior", 0.72)],
        )
        assert 0 <= breakdown.final_score <= 1
        assert breakdown.final_score >= breakdown.base_score


class TestFeedbackLoop:
    def test_feedback_processing_auto_resolves_high_confidence(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(output_dir=tmp_path)
        orchestrator = ECOQualityOrchestrator(config)
        feedback = [
            {
                "alias": "dev frontend senior",
                "canonical": "desenvolvedor frontend",
                "confidence_rating": 5,
                "posting_volume": 10,
                "last_seen": datetime.utcnow().isoformat(),
                "evidence": [{"source": "linkedin", "confidence": 0.92, "weight": 2}],
            },
            {
                "alias": "cientista de dados",
                "canonical": "data scientist",
                "confidence_rating": 2,
            },
        ]
        payload = orchestrator.processFeedbackLoop(feedback)
        assert len(payload["auto_resolved"]) == 1
        assert len(payload["needs_manual_review"]) == 1


class TestClusteringValidation:
    def test_clustering_validator_produces_metrics(self, tmp_path: Path) -> None:
        gold_standard = {
            "records": [
                {"alias": "dev backend", "eco_id": "ECO.A"},
                {"alias": "cientista de dados", "eco_id": "ECO.B"},
            ]
        }
        clusters = {
            "clusters": {
                "1": {
                    "eco_id": "ECO.A",
                    "aliases": [
                        {"alias": "dev backend", "normalized": "dev backend", "confidence": 0.8},
                        {"alias": "desenvolvedor backend", "normalized": "desenvolvedor backend", "confidence": 0.7},
                    ],
                    "similarities": [0.9, 0.85],
                },
                "2": {
                    "eco_id": "ECO.C",
                    "aliases": [
                        {"alias": "cientista de dados", "normalized": "cientista de dados", "confidence": 0.6}
                    ],
                    "similarities": [0.7],
                },
            }
        }
        gold_path = tmp_path / "gold.json"
        clusters_path = tmp_path / "clusters.json"
        gold_path.write_text(json.dumps(gold_standard), encoding="utf-8")
        clusters_path.write_text(json.dumps(clusters), encoding="utf-8")
        config = ClusteringValidatorConfig(
            gold_standard_path=gold_path,
            cluster_results_path=clusters_path,
            output_dir=tmp_path,
        )
        validator = ClusteringValidator(config)
        metrics = validator.validateOccupationMappings()
        assert "precision" in metrics
        report = validator.generateValidationReport()
        assert report["occupation_metrics"]["true_positive"] >= 1


class TestTemplateAccuracy:
    def test_template_accuracy_scores(self, tmp_path: Path) -> None:
        templates = {
            "templates": [
                {
                    "eco_id": "ECO.A",
                    "required_skills": ["React", "TypeScript"],
                    "preferred_skills": ["GraphQL"],
                    "min_years_experience": 3,
                    "max_years_experience": 6,
                }
            ]
        }
        postings = [
            {
                "eco_id": "ECO.A",
                "required_skills": ["React", "TypeScript", "Redux"],
                "preferred_skills": ["GraphQL"],
                "min_years_experience": 4,
                "max_years_experience": 7,
                "collected_at": datetime.utcnow().isoformat(),
            }
        ]
        template_path = tmp_path / "templates.json"
        postings_path = tmp_path / "postings.json"
        template_path.write_text(json.dumps(templates), encoding="utf-8")
        postings_path.write_text(json.dumps(postings), encoding="utf-8")
        config = TemplateAccuracyValidatorConfig(
            template_path=template_path,
            job_postings_path=postings_path,
            output_dir=tmp_path,
        )
        validator = TemplateAccuracyValidator(config)
        report = validator.generateValidationReport()
        assert report["quality_score"]["score"] >= 0
        assert "recommendations" in report


class TestAdminUI:
    def test_dashboard_sections_listed(self) -> None:
        content = Path('headhunter-ui/src/components/Admin/AdminPage.tsx').read_text(encoding='utf-8')
        assert 'Validation Queue' in content
        assert 'Feedback Management' in content
        assert 'Clustering Validation' in content
        assert 'Template Accuracy' in content


class TestFirebaseFunctions:
    def test_callable_exports_declared(self) -> None:
        source = Path('functions/src/eco-validation.ts').read_text(encoding='utf-8')
        for name in [
            'export const getValidationQueue',
            'export const updateValidationItem',
            'export const submitFeedback',
            'export const listFeedback',
            'export const updateFeedback',
            'export const getQualityMetrics',
            'export const runClusteringValidation',
            'export const validateTemplateAccuracy',
            'export const getECOStatistics',
            'export const assignValidationItems',
            'export const exportValidationReport',
        ]:
            assert name in source
