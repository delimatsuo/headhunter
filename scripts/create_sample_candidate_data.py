#!/usr/bin/env python3
"""
Create sample candidate data in Firestore for Phase 2 testing.

Generates realistic candidate profiles with varying skills and experience.
Prints created candidate IDs for use with /process/batch.
"""

import argparse
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any

from google.cloud import firestore


FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Jamie",
    "Cameron", "Sydney", "Drew", "Emerson", "Quinn", "Rowan", "Shawn"
]
LAST_NAMES = [
    "Smith", "Johnson", "Lee", "Garcia", "Martinez", "Brown", "Davis", "Rodriguez",
    "Miller", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson"
]

SKILLS = [
    "Python", "TypeScript", "Go", "Java", "Kotlin", "Rust", "SQL", "NoSQL",
    "GCP", "AWS", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD",
    "React", "Vue", "Svelte", "Node.js", "Django", "Flask", "FastAPI"
]

SOFT_SKILLS = [
    "Leadership", "Communication", "Collaboration", "Problem Solving", "Adaptability",
    "Mentoring", "Stakeholder Management", "Ownership", "Decision Making"
]


def rand_id(prefix: str = "cand") -> str:
    return f"{prefix}-" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


def build_resume(name: str, tech: list, years: int) -> str:
    return (
        f"{name} is a software engineer with {years} years of experience.\n"
        f"Core skills: {', '.join(tech[:6])}.\n"
        "Worked on scalable backend services, APIs, and cloud infrastructure.\n"
        "Demonstrated ownership, mentoring, and cross-functional collaboration.\n"
    )


def make_candidate(org_id: str) -> Dict[str, Any]:
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    years = random.randint(1, 18)
    tech = random.sample(SKILLS, k=random.randint(5, 10))
    soft = random.sample(SOFT_SKILLS, k=random.randint(2, 5))

    return {
        "candidate_id": rand_id("cand"),
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}@example.com",
        "resume_text": build_resume(name, tech, years),
        "recruiter_comments": f"Strong in {tech[0]} and {tech[1]}. Soft skills: {', '.join(soft)}.",
        "org_id": org_id,
        "uploaded_at": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat() + "Z",
        "status": "pending_enrichment",
        "metadata": {
            "years_experience": years,
            "technical_skills": tech,
            "soft_skills": soft,
            "source": random.choice(["referral", "linkedin", "inbound"]),
            "location": random.choice(["SF", "NYC", "Remote", "Austin", "Seattle"]),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Create sample candidates in Firestore")
    parser.add_argument("--org", required=True, help="Organization ID for the candidates")
    parser.add_argument("--count", type=int, default=5, help="Number of candidates to create")
    parser.add_argument("--collection", default="candidates", help="Firestore collection name")
    parser.add_argument("--project-id", default=None, help="GCP project ID (optional)")
    args = parser.parse_args()

    client = firestore.Client(project=args.project_id) if args.project_id else firestore.Client()
    created = []
    for _ in range(args.count):
        cand = make_candidate(args.org)
        doc_ref = client.collection(args.collection).document(cand["candidate_id"])
        doc_ref.set(cand)
        created.append(cand["candidate_id"])

    print("Created candidate IDs:")
    for cid in created:
        print(cid)


if __name__ == "__main__":
    main()

