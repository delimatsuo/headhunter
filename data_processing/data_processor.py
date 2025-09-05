#!/usr/bin/env python3
"""
Headhunter Data Processor
Prepares Workable export data for LLM analysis by creating enriched candidate profiles.
"""

import pandas as pd
import json
import os
import glob
from pathlib import Path
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CandidateDataProcessor:
    def __init__(self, csv_dir: str, output_dir: str):
        self.csv_dir = Path(csv_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_candidates(self) -> pd.DataFrame:
        """Load and merge all candidate CSV files."""
        candidate_files = list(self.csv_dir.glob("Ella_Executive_Search_candidates_*.csv"))
        logger.info(f"Found {len(candidate_files)} candidate CSV files")

        dfs = []
        for file in candidate_files:
            df = pd.read_csv(file, low_memory=False)
            dfs.append(df)

        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(combined_df)} total candidates")
        return combined_df

    def load_comments(self) -> pd.DataFrame:
        """Load and merge all comments CSV files."""
        comment_files = list(self.csv_dir.glob("Ella_Executive_Search_comments-*.csv"))
        logger.info(f"Found {len(comment_files)} comment CSV files")

        dfs = []
        for file in comment_files:
            df = pd.read_csv(file, low_memory=False)
            dfs.append(df)

        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(combined_df)} total comments")
        return combined_df

    def merge_candidate_comments(self, candidates_df: pd.DataFrame, comments_df: pd.DataFrame) -> pd.DataFrame:
        """Merge candidates with their comments."""
        # Group comments by candidate_id
        comments_grouped = comments_df.groupby('candidate_id')['body'].apply(list).reset_index()
        comments_grouped.columns = ['id', 'comments']

        # Merge with candidates
        merged_df = candidates_df.merge(comments_grouped, on='id', how='left')
        merged_df['comments'] = merged_df['comments'].fillna('').apply(lambda x: x if isinstance(x, list) else [])

        logger.info(f"Merged data: {len(merged_df)} candidates with comments")
        return merged_df

    def find_resume_path(self, candidate_id: str, job_id: str = None) -> str:
        """Find resume file path for a candidate."""
        resume_base = self.csv_dir.parent / "files_1" / "resumes"

        # Try different path patterns
        possible_paths = [
            resume_base / str(candidate_id),
            resume_base / str(job_id) / str(candidate_id) if job_id else None,
        ]

        for path in possible_paths:
            if path and path.exists():
                # Find the first file in the directory
                files = list(path.glob("*"))
                if files:
                    return str(files[0].relative_to(self.csv_dir.parent))

        return None

    def create_enriched_profile(self, row: pd.Series) -> Dict[str, Any]:
        """Create an enriched candidate profile optimized for LLM analysis."""
        profile = {
            "candidate_id": str(row['id']),
            "name": row['name'] or "",
            "email": row['email'] or "",
            "headline": row['headline'] or "",
            "summary": row['summary'] or "",
            "phone": row['phone'] or "",
            "address": row['address'] or "",

            # Structured data
            "education": self._parse_education(row['education']),
            "experience": self._parse_experience(row['experience']),
            "skills": row['skills'] or "",
            "tags": row['tags'] or "",

            # Social profiles
            "social_profiles": self._parse_social_profiles(row['social_profiles']),

            # Resume file path
            "resume_path": self.find_resume_path(str(row['id']), str(row['job_id']) if pd.notna(row['job_id']) else None),

            # Recruiter insights from comments
            "recruiter_notes": row['comments'] if isinstance(row['comments'], list) else [],

            # Metadata
            "source": row['source'] or "",
            "stage": row['stage'] or "",
            "job_title": row.get('job', ""),
            "created_at": row['created_at'],
            "disqualified": bool(row['disqualified']),
        }

        return profile

    def _parse_education(self, education_str: str) -> List[Dict]:
        """Parse education string into structured format."""
        if not education_str or pd.isna(education_str):
            return []

        # This is a simple parser - you might want to enhance this
        return [{"raw": education_str}]

    def _parse_experience(self, experience_str: str) -> List[Dict]:
        """Parse experience string into structured format."""
        if not experience_str or pd.isna(experience_str):
            return []

        # This is a simple parser - you might want to enhance this
        return [{"raw": experience_str}]

    def _parse_social_profiles(self, profiles_str: str) -> List[Dict]:
        """Parse social profiles JSON string."""
        if not profiles_str or pd.isna(profiles_str):
            return []

        try:
            return json.loads(profiles_str)
        except:
            return []

    def process_and_save(self, limit: int = None) -> None:
        """Main processing pipeline."""
        logger.info("Starting data processing...")

        # Load data
        candidates_df = self.load_candidates()
        comments_df = self.load_comments()

        # Merge data
        merged_df = self.merge_candidate_comments(candidates_df, comments_df)

        # Limit for testing
        if limit:
            merged_df = merged_df.head(limit)

        # Create enriched profiles
        profiles = []
        for idx, row in merged_df.iterrows():
            if idx % 100 == 0:
                logger.info(f"Processing candidate {idx}/{len(merged_df)}")

            profile = self.create_enriched_profile(row)
            profiles.append(profile)

        # Save as JSON Lines for efficient processing
        output_file = self.output_dir / "enriched_candidates.jsonl"
        with open(output_file, 'w', encoding='utf-8') as f:
            for profile in profiles:
                f.write(json.dumps(profile, ensure_ascii=False) + '\n')

        logger.info(f"Saved {len(profiles)} enriched profiles to {output_file}")

        # Save summary statistics
        self._save_summary_stats(merged_df, profiles)

    def _save_summary_stats(self, df: pd.DataFrame, profiles: List[Dict]) -> None:
        """Save summary statistics of the processed data."""
        stats = {
            "total_candidates": len(df),
            "candidates_with_comments": len([p for p in profiles if p['recruiter_notes']]),
            "candidates_with_resumes": len([p for p in profiles if p['resume_path']]),
            "stage_distribution": df['stage'].value_counts().to_dict() if 'stage' in df.columns else {},
            "source_distribution": df['source'].value_counts().head(10).to_dict() if 'source' in df.columns else {},
        }

        stats_file = self.output_dir / "processing_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved processing statistics to {stats_file}")

def main():
    # Configuration
    csv_dir = Path("/Users/delimatsuo/Documents/Coding/headhunter/CSV files/505039_Ella_Executive_Search_CSVs_1")
    output_dir = Path("/Users/delimatsuo/Documents/Coding/headhunter/data_processing/output")

    # Process data
    processor = CandidateDataProcessor(csv_dir, output_dir)
    processor.process_and_save(limit=1000)  # Remove limit for full processing

if __name__ == "__main__":
    main()
