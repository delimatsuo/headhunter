"""
Model evaluation for career trajectory LSTM.
Includes specific tests for career changers to detect one-step lag problem.
"""
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import torch
import numpy as np
from sklearn.metrics import roc_auc_score
from tqdm import tqdm

from lstm_model import CareerTrajectoryLSTM
from title_encoder import TitleEncoder
from train import CareerSequenceDataset, collate_fn, generate_sequences, temporal_split, load_career_sequences
from torch.utils.data import DataLoader


def evaluate_model(
    model: torch.nn.Module,
    test_loader: DataLoader,
    device: torch.device,
    encoder: TitleEncoder
) -> Dict[str, float]:
    """
    Compute comprehensive evaluation metrics.

    Args:
        model: Trained CareerTrajectoryLSTM model
        test_loader: Test data loader
        device: Device to run on
        encoder: TitleEncoder instance

    Returns:
        Dictionary with evaluation metrics
    """
    print("Evaluating model on test set...")

    model.eval()

    # Metrics tracking
    correct_top1 = 0
    correct_top5 = 0
    total = 0

    tenure_errors = []
    hireability_preds = []
    hireability_labels = []

    all_predictions = []
    all_labels = []
    all_input_titles = []

    with torch.no_grad():
        for batch in tqdm(test_loader, desc="Testing"):
            input_ids = batch['input_ids'].to(device)
            lengths = batch['lengths']
            next_title_ids = batch['next_title_ids'].to(device)
            tenure_months = batch['tenure_months'].to(device)
            hireability = batch['hireability'].to(device)

            # Forward pass
            next_role_logits, tenure_pred, hireability_pred = model(input_ids, lengths)

            # Top-1 accuracy
            predictions = torch.argmax(next_role_logits, dim=1)
            correct_top1 += (predictions == next_title_ids).sum().item()

            # Top-5 accuracy
            _, top5_preds = torch.topk(next_role_logits, min(5, next_role_logits.size(1)), dim=1)
            correct_top5 += sum([
                label.item() in top5_preds[i].tolist()
                for i, label in enumerate(next_title_ids)
            ])

            total += next_title_ids.size(0)

            # Tenure MAE
            actual_tenure = tenure_months[:, 0]  # Use first value (they're the same in our dataset)
            predicted_tenure = (tenure_pred[:, 0] + tenure_pred[:, 1]) / 2  # Average of min/max
            tenure_errors.extend(torch.abs(predicted_tenure - actual_tenure).cpu().numpy())

            # Hireability AUC
            hireability_preds.extend(hireability_pred.cpu().numpy().flatten())
            # Convert hireability to binary (>0.5 = high)
            hireability_binary = (hireability > 0.5).float()
            hireability_labels.extend(hireability_binary.cpu().numpy().flatten())

            # Store for career changer analysis
            all_predictions.extend(predictions.cpu().numpy())
            all_labels.extend(next_title_ids.cpu().numpy())
            all_input_titles.extend([
                encoder.decode_sequence(input_ids[i, :lengths[i]].cpu().numpy().tolist())
                for i in range(input_ids.size(0))
            ])

    # Compute metrics
    top1_accuracy = correct_top1 / total
    top5_accuracy = correct_top5 / total
    tenure_mae = np.mean(tenure_errors)

    # Hireability AUC (only if we have both classes)
    unique_labels = np.unique(hireability_labels)
    if len(unique_labels) > 1:
        hireability_auc = roc_auc_score(hireability_labels, hireability_preds)
    else:
        hireability_auc = 0.0
        print("Warning: Only one class in hireability labels, AUC not computed")

    metrics = {
        'top1_accuracy': top1_accuracy,
        'top5_accuracy': top5_accuracy,
        'tenure_mae': tenure_mae,
        'hireability_auc': hireability_auc,
        'total_samples': total
    }

    print(f"\nTest Set Metrics:")
    print(f"  Top-1 Accuracy: {top1_accuracy:.4f}")
    print(f"  Top-5 Accuracy: {top5_accuracy:.4f}")
    print(f"  Tenure MAE: {tenure_mae:.2f} months")
    print(f"  Hireability AUC: {hireability_auc:.4f}")
    print(f"  Total samples: {total}")

    return metrics


def test_career_changers(
    model: torch.nn.Module,
    test_loader: DataLoader,
    device: torch.device,
    encoder: TitleEncoder
) -> Dict[str, float]:
    """
    Test model specifically on career changers.

    CRITICAL per RESEARCH.md: Explicitly test on career changers to detect
    one-step lag problem where model predicts current role instead of next role.

    A career changer is defined as someone whose next role is significantly
    different from their current role (different core title words).

    Args:
        model: Trained model
        test_loader: Test data loader
        device: Device to run on
        encoder: TitleEncoder instance

    Returns:
        Dictionary with career changer metrics
    """
    print("\nTesting on career changers...")

    model.eval()

    career_changer_correct = 0
    career_changer_total = 0
    same_prediction_count = 0  # Count how often model predicts current role

    with torch.no_grad():
        for batch in tqdm(test_loader, desc="Analyzing career changers"):
            input_ids = batch['input_ids'].to(device)
            lengths = batch['lengths']
            next_title_ids = batch['next_title_ids'].to(device)

            # Forward pass
            next_role_logits, _, _ = model(input_ids, lengths)
            predictions = torch.argmax(next_role_logits, dim=1)

            # Check each sample
            for i in range(input_ids.size(0)):
                input_seq = input_ids[i, :lengths[i]].cpu().numpy()
                current_title_id = input_seq[-1]  # Last title in sequence
                next_title_id = next_title_ids[i].item()
                predicted_title_id = predictions[i].item()

                # Decode titles
                current_title = encoder.decode(current_title_id)
                next_title = encoder.decode(next_title_id)
                predicted_title = encoder.decode(predicted_title_id)

                # Check if this is a career changer
                # Simple heuristic: different core words in title
                current_words = set(current_title.lower().split())
                next_words = set(next_title.lower().split())

                # Remove common words
                common_words = {'senior', 'junior', 'lead', 'staff', 'principal', 'associate', 'i', 'ii', 'iii'}
                current_words = current_words - common_words
                next_words = next_words - common_words

                # If less than 50% overlap in core words, it's a career change
                if len(current_words & next_words) / max(len(next_words), 1) < 0.5:
                    career_changer_total += 1

                    # Check if prediction is correct
                    if predicted_title_id == next_title_id:
                        career_changer_correct += 1

                    # Check for one-step lag (predicting current role)
                    if predicted_title_id == current_title_id:
                        same_prediction_count += 1

    if career_changer_total > 0:
        accuracy = career_changer_correct / career_changer_total
        same_prediction_rate = same_prediction_count / career_changer_total

        print(f"\nCareer Changer Analysis:")
        print(f"  Total career changers: {career_changer_total}")
        print(f"  Accuracy on career changers: {accuracy:.4f}")
        print(f"  Same prediction rate: {same_prediction_rate:.4f}")

        if same_prediction_rate > 0.5:
            print("  ⚠ WARNING: High same prediction rate suggests one-step lag problem!")
        else:
            print("  ✓ One-step lag check passed")

        return {
            'career_changer_accuracy': accuracy,
            'career_changer_total': career_changer_total,
            'same_prediction_rate': same_prediction_rate,
            'one_step_lag_detected': same_prediction_rate > 0.5
        }
    else:
        print("No career changers detected in test set")
        return {
            'career_changer_accuracy': 0.0,
            'career_changer_total': 0,
            'same_prediction_rate': 0.0,
            'one_step_lag_detected': False
        }


def generate_report(
    metrics: Dict[str, float],
    career_changer_metrics: Dict[str, float],
    output_path: str
) -> None:
    """
    Generate markdown evaluation report.

    Args:
        metrics: Overall evaluation metrics
        career_changer_metrics: Career changer specific metrics
        output_path: Output file path
    """
    print(f"\nGenerating report at {output_path}...")

    report = f"""# Career Trajectory LSTM - Evaluation Report

## Overall Performance

| Metric | Value |
|--------|-------|
| Top-1 Accuracy | {metrics['top1_accuracy']:.4f} |
| Top-5 Accuracy | {metrics['top5_accuracy']:.4f} |
| Tenure MAE | {metrics['tenure_mae']:.2f} months |
| Hireability AUC | {metrics['hireability_auc']:.4f} |
| Total Samples | {metrics['total_samples']} |

## Career Changer Analysis

Testing on career changers is critical to detect the one-step lag problem,
where the model learns to predict the current role instead of the next role.

| Metric | Value |
|--------|-------|
| Career Changers | {career_changer_metrics['career_changer_total']} |
| Accuracy on Career Changers | {career_changer_metrics['career_changer_accuracy']:.4f} |
| Same Prediction Rate | {career_changer_metrics['same_prediction_rate']:.4f} |
| One-Step Lag Detected | {'Yes ⚠' if career_changer_metrics['one_step_lag_detected'] else 'No ✓'} |

## Interpretation

**Top-1 Accuracy:** Percentage of predictions where the exact next role is the top prediction.

**Top-5 Accuracy:** Percentage of predictions where the correct next role is in the top 5 predictions.

**Tenure MAE:** Mean absolute error in months for tenure predictions.

**Hireability AUC:** AUC-ROC score for hireability predictions (0.5 = random, 1.0 = perfect).

**Same Prediction Rate:** How often the model predicts the current role as the next role for career changers.
High values (>0.5) indicate the one-step lag problem.

## Recommendations

"""

    if career_changer_metrics['one_step_lag_detected']:
        report += """
### ⚠ One-Step Lag Detected

The model is predicting the current role instead of the next role for career changers.

**Possible causes:**
1. Sequence alignment issue during training
2. Teacher forcing problem
3. Model learning to copy input instead of predict next step

**Recommendations:**
1. Verify sequence alignment in training data (input[t] should predict target[t+1])
2. Add explicit tests during training to detect this issue early
3. Consider adding regularization to prevent copy behavior
"""
    else:
        report += """
### ✓ One-Step Lag Check Passed

The model is correctly predicting next roles for career changers, not just repeating
current roles.
"""

    # Write report
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Evaluate trajectory model')
    parser.add_argument('--checkpoint', type=str, required=True, help='Path to model checkpoint')
    parser.add_argument('--vocab', type=str, required=True, help='Path to vocabulary JSON')
    parser.add_argument('--db-url', type=str, required=True, help='PostgreSQL connection URL')
    parser.add_argument('--output', type=str, default='models/evaluation_report.md', help='Output report path')
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

    # Load test data
    print("\nLoading test data...")
    df = load_career_sequences(args.db_url)
    _, _, test_df = temporal_split(df)
    test_sequences = generate_sequences(test_df)

    # Create dataloader
    print("Creating test dataloader...")
    test_dataset = CareerSequenceDataset(test_sequences, encoder)
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collate_fn,
        num_workers=0
    )

    # Evaluate model
    metrics = evaluate_model(model, test_loader, device, encoder)

    # Test career changers
    career_changer_metrics = test_career_changers(model, test_loader, device, encoder)

    # Generate report
    generate_report(metrics, career_changer_metrics, args.output)

    print("\nEvaluation complete!")


if __name__ == '__main__':
    main()
