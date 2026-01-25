"""
Confidence calibration for career trajectory model.
Uses isotonic regression to ensure predicted probabilities match actual frequencies.
"""
import argparse
import pickle
from pathlib import Path
from typing import Tuple
import torch
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
from tqdm import tqdm

from lstm_model import CareerTrajectoryLSTM
from title_encoder import TitleEncoder
from train import CareerSequenceDataset, collate_fn, generate_sequences, temporal_split, load_career_sequences
from torch.utils.data import DataLoader


def train_calibrator(
    model: torch.nn.Module,
    val_loader: DataLoader,
    device: torch.device
) -> IsotonicRegression:
    """
    Train isotonic regression calibrator on validation set.

    Args:
        model: Trained CareerTrajectoryLSTM model
        val_loader: Validation data loader
        device: Device to run on

    Returns:
        Fitted IsotonicRegression calibrator
    """
    print("Collecting predictions for calibration...")

    model.eval()
    all_confidences = []
    all_correct = []

    with torch.no_grad():
        for batch in tqdm(val_loader, desc="Collecting predictions"):
            input_ids = batch['input_ids'].to(device)
            lengths = batch['lengths']
            next_title_ids = batch['next_title_ids'].to(device)

            # Forward pass
            next_role_logits, _, _ = model(input_ids, lengths)

            # Get probabilities and predictions
            probs = torch.softmax(next_role_logits, dim=1)
            max_probs, predictions = probs.max(dim=1)

            # Check correctness
            correct = (predictions == next_title_ids).cpu().numpy()

            all_confidences.extend(max_probs.cpu().numpy())
            all_correct.extend(correct)

    all_confidences = np.array(all_confidences)
    all_correct = np.array(all_correct)

    print(f"\nCollected {len(all_confidences)} predictions")
    print(f"Raw accuracy: {all_correct.mean():.4f}")
    print(f"Raw confidence (mean): {all_confidences.mean():.4f}")

    # Train isotonic regression
    print("\nTraining isotonic regression calibrator...")
    calibrator = IsotonicRegression(out_of_bounds='clip')
    calibrator.fit(all_confidences, all_correct)

    print("Calibrator trained successfully")

    return calibrator


def save_calibrator(calibrator: IsotonicRegression, path: str) -> None:
    """
    Save calibrator to pickle file.

    Args:
        calibrator: Fitted IsotonicRegression instance
        path: Output file path
    """
    with open(path, 'wb') as f:
        pickle.dump(calibrator, f)
    print(f"Calibrator saved to {path}")


def load_calibrator(path: str) -> IsotonicRegression:
    """
    Load calibrator from pickle file.

    Args:
        path: Input file path

    Returns:
        Loaded IsotonicRegression instance
    """
    with open(path, 'rb') as f:
        calibrator = pickle.load(f)
    print(f"Calibrator loaded from {path}")
    return calibrator


def evaluate_calibration(
    calibrator: IsotonicRegression,
    raw_probs: np.ndarray,
    labels: np.ndarray,
    num_bins: int = 10
) -> dict:
    """
    Evaluate calibration quality.

    Computes Expected Calibration Error (ECE) and Brier score.
    Target: ECE < 0.05 per RESEARCH.md

    Args:
        calibrator: Fitted calibrator
        raw_probs: Raw model confidences
        labels: True correctness labels (0 or 1)
        num_bins: Number of bins for ECE calculation

    Returns:
        Dictionary with calibration metrics
    """
    print("\nEvaluating calibration...")

    # Get calibrated probabilities
    calibrated_probs = calibrator.predict(raw_probs)

    # Compute Brier scores
    raw_brier = brier_score_loss(labels, raw_probs)
    calibrated_brier = brier_score_loss(labels, calibrated_probs)

    print(f"Brier score (raw): {raw_brier:.4f}")
    print(f"Brier score (calibrated): {calibrated_brier:.4f}")
    print(f"Brier improvement: {(raw_brier - calibrated_brier) / raw_brier * 100:.1f}%")

    # Compute ECE (Expected Calibration Error)
    ece_raw = compute_ece(raw_probs, labels, num_bins)
    ece_calibrated = compute_ece(calibrated_probs, labels, num_bins)

    print(f"\nECE (raw): {ece_raw:.4f}")
    print(f"ECE (calibrated): {ece_calibrated:.4f}")

    if ece_calibrated < 0.05:
        print("✓ ECE target met (<0.05)")
    else:
        print(f"✗ ECE target not met (expected <0.05)")

    return {
        'brier_raw': raw_brier,
        'brier_calibrated': calibrated_brier,
        'ece_raw': ece_raw,
        'ece_calibrated': ece_calibrated,
        'ece_target_met': ece_calibrated < 0.05
    }


def compute_ece(probs: np.ndarray, labels: np.ndarray, num_bins: int = 10) -> float:
    """
    Compute Expected Calibration Error (ECE).

    Args:
        probs: Predicted probabilities
        labels: True labels (0 or 1)
        num_bins: Number of bins

    Returns:
        ECE value
    """
    bin_boundaries = np.linspace(0, 1, num_bins + 1)
    ece = 0.0
    total_samples = len(probs)

    for i in range(num_bins):
        lower = bin_boundaries[i]
        upper = bin_boundaries[i + 1]

        # Find samples in this bin
        in_bin = (probs >= lower) & (probs < upper)
        if i == num_bins - 1:  # Include upper boundary in last bin
            in_bin = in_bin | (probs == upper)

        bin_size = in_bin.sum()

        if bin_size > 0:
            # Average confidence in bin
            avg_confidence = probs[in_bin].mean()
            # Average accuracy in bin
            avg_accuracy = labels[in_bin].mean()
            # Weighted contribution to ECE
            ece += (bin_size / total_samples) * abs(avg_confidence - avg_accuracy)

    return ece


def main():
    parser = argparse.ArgumentParser(description='Train confidence calibrator for trajectory model')
    parser.add_argument('--checkpoint', type=str, required=True, help='Path to model checkpoint')
    parser.add_argument('--vocab', type=str, required=True, help='Path to vocabulary JSON')
    parser.add_argument('--db-url', type=str, required=True, help='PostgreSQL connection URL')
    parser.add_argument('--output', type=str, required=True, help='Output path for calibrator (.pkl)')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    args = parser.parse_args()

    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load vocabulary
    print("\nLoading vocabulary...")
    encoder = TitleEncoder()
    encoder.load(args.vocab)

    # Load model
    print("Loading model...")
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model = CareerTrajectoryLSTM(vocab_size=encoder.vocab_size).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    # Load data
    print("\nLoading data...")
    df = load_career_sequences(args.db_url)
    _, val_df, _ = temporal_split(df)
    val_sequences = generate_sequences(val_df)

    # Create dataloader
    print("Creating validation dataloader...")
    val_dataset = CareerSequenceDataset(val_sequences, encoder)
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collate_fn,
        num_workers=0
    )

    # Train calibrator
    calibrator = train_calibrator(model, val_loader, device)

    # Save calibrator
    save_calibrator(calibrator, args.output)

    # Evaluate calibration
    print("\nEvaluating on validation set...")

    # Collect predictions for evaluation
    model.eval()
    all_raw_probs = []
    all_labels = []

    with torch.no_grad():
        for batch in tqdm(val_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            lengths = batch['lengths']
            next_title_ids = batch['next_title_ids'].to(device)

            next_role_logits, _, _ = model(input_ids, lengths)
            probs = torch.softmax(next_role_logits, dim=1)
            max_probs, predictions = probs.max(dim=1)

            correct = (predictions == next_title_ids).cpu().numpy()

            all_raw_probs.extend(max_probs.cpu().numpy())
            all_labels.extend(correct)

    metrics = evaluate_calibration(
        calibrator,
        np.array(all_raw_probs),
        np.array(all_labels)
    )

    print("\nCalibration complete!")


if __name__ == '__main__':
    main()
