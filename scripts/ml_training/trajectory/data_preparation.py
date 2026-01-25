"""
Data preparation for career trajectory LSTM training.
Handles loading career sequences from PostgreSQL, temporal splitting, and sequence generation.
"""
import json
from typing import List, Tuple, Dict, Any
from datetime import datetime
import pandas as pd
import psycopg2
from tqdm import tqdm


def load_career_sequences(db_url: str) -> pd.DataFrame:
    """
    Load career sequences from PostgreSQL candidates table.

    Args:
        db_url: PostgreSQL connection string

    Returns:
        DataFrame with columns: candidate_id, title_sequence, end_dates, tenure_durations
    """
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # Query candidates with work history
    query = """
        SELECT id, work_history
        FROM candidates
        WHERE work_history IS NOT NULL
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    candidates = []

    for candidate_id, work_history in tqdm(rows, desc="Loading career sequences"):
        if isinstance(work_history, str):
            work_history = json.loads(work_history)

        if not work_history or len(work_history) < 2:
            continue  # Need at least 2 roles for prediction

        # Sort by start date (oldest first)
        sorted_history = sorted(work_history, key=lambda x: x.get('start_date', ''))

        titles = []
        end_dates = []
        tenure_durations = []

        for i, job in enumerate(sorted_history):
            title = job.get('title', '').strip()
            if not title:
                continue

            titles.append(title)
            end_dates.append(job.get('end_date'))

            # Calculate tenure duration if possible
            if 'start_date' in job and 'end_date' in job:
                try:
                    start = datetime.fromisoformat(job['start_date'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(job['end_date'].replace('Z', '+00:00'))
                    months = (end.year - start.year) * 12 + (end.month - start.month)
                    tenure_durations.append(max(1, months))  # At least 1 month
                except:
                    tenure_durations.append(None)
            else:
                tenure_durations.append(None)

        if len(titles) >= 2:
            candidates.append({
                'candidate_id': candidate_id,
                'title_sequence': titles,
                'end_dates': end_dates,
                'tenure_durations': tenure_durations,
                'latest_end_date': end_dates[-1] if end_dates[-1] else None
            })

    cursor.close()
    conn.close()

    df = pd.DataFrame(candidates)
    print(f"Loaded {len(df)} candidates with 2+ roles")
    return df


def temporal_split(
    df: pd.DataFrame,
    train_cutoff: str = '2024-01-01',
    val_cutoff: str = '2024-07-01'
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data by time to prevent temporal leakage.

    CRITICAL: This splits BEFORE generating input-output sequences.
    Splitting after sequence generation would leak future information.

    Args:
        df: DataFrame with career sequences
        train_cutoff: ISO date string - careers ending before this go to train
        val_cutoff: ISO date string - careers ending before this go to val

    Returns:
        (train_df, val_df, test_df) tuple
    """
    train_cutoff_date = pd.to_datetime(train_cutoff)
    val_cutoff_date = pd.to_datetime(val_cutoff)

    # Convert latest_end_date to datetime
    df['latest_end_date_dt'] = pd.to_datetime(df['latest_end_date'], errors='coerce')

    # Split by latest experience end date
    train_df = df[df['latest_end_date_dt'] < train_cutoff_date].copy()
    val_df = df[
        (df['latest_end_date_dt'] >= train_cutoff_date) &
        (df['latest_end_date_dt'] < val_cutoff_date)
    ].copy()
    test_df = df[df['latest_end_date_dt'] >= val_cutoff_date].copy()

    # Also include rows with missing dates in test (most recent, safest)
    missing_dates = df[df['latest_end_date_dt'].isna()].copy()
    test_df = pd.concat([test_df, missing_dates])

    print(f"Split: {len(train_df)} train, {len(val_df)} val, {len(test_df)} test")
    print(f"Train cutoff: {train_cutoff}, Val cutoff: {val_cutoff}")

    return train_df, val_df, test_df


def generate_sequences(df: pd.DataFrame) -> List[Tuple[List[str], str, int, str]]:
    """
    Generate training sequences from career data.

    For each candidate: titles[:-1] predicts titles[-1]

    Args:
        df: DataFrame with title_sequence column

    Returns:
        List of (input_titles, next_title, tenure_months, candidate_id) tuples
    """
    sequences = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Generating sequences"):
        titles = row['title_sequence']
        tenure_durations = row['tenure_durations']
        candidate_id = row['candidate_id']

        if len(titles) < 2:
            continue

        # Input: all titles except last, Output: last title
        input_titles = titles[:-1]
        next_title = titles[-1]

        # Tenure for next role (if available)
        tenure_months = tenure_durations[-1] if tenure_durations[-1] is not None else 24  # Default 24 months

        sequences.append((input_titles, next_title, tenure_months, candidate_id))

    print(f"Generated {len(sequences)} training sequences")
    return sequences


if __name__ == '__main__':
    """Example usage for testing"""
    import os
    from dotenv import load_dotenv

    load_dotenv()
    db_url = os.getenv('POSTGRES_URL')

    if not db_url:
        print("Error: POSTGRES_URL not set in environment")
        exit(1)

    print("Loading career sequences from database...")
    df = load_career_sequences(db_url)

    print("\nSplitting data temporally...")
    train_df, val_df, test_df = temporal_split(df)

    print("\nGenerating training sequences...")
    train_sequences = generate_sequences(train_df)
    print(f"Sample: {train_sequences[0] if train_sequences else 'No sequences'}")
