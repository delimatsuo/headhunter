"""
Training script for career trajectory LSTM model.
Includes time-aware splits, multi-task loss, and early stopping.
"""
import argparse
import os
from pathlib import Path
from typing import Tuple, List
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
from tqdm import tqdm

from data_preparation import load_career_sequences, temporal_split, generate_sequences
from title_encoder import TitleEncoder
from lstm_model import CareerTrajectoryLSTM


class CareerSequenceDataset(Dataset):
    """Dataset for career sequences."""

    def __init__(self, sequences: List[Tuple], encoder: TitleEncoder):
        """
        Args:
            sequences: List of (input_titles, next_title, tenure_months, candidate_id) tuples
            encoder: TitleEncoder for encoding titles
        """
        self.sequences = sequences
        self.encoder = encoder

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        input_titles, next_title, tenure_months, candidate_id = self.sequences[idx]

        # Encode input titles
        input_ids = self.encoder.encode_sequence(input_titles)
        next_title_id = self.encoder.encode(next_title)

        # Hireability (simplified: assume high if tenure > 12 months, else low)
        hireability = 1.0 if tenure_months >= 12 else 0.5

        return {
            'input_ids': torch.tensor(input_ids, dtype=torch.long),
            'length': len(input_ids),
            'next_title_id': torch.tensor(next_title_id, dtype=torch.long),
            'tenure_months': torch.tensor([tenure_months, tenure_months], dtype=torch.float32),  # [min, max]
            'hireability': torch.tensor([hireability], dtype=torch.float32),
            'candidate_id': candidate_id
        }


def collate_fn(batch):
    """Collate function to pad variable length sequences."""
    # Find max length in batch
    max_len = max(item['length'] for item in batch)

    # Pad sequences
    input_ids = []
    lengths = []
    next_title_ids = []
    tenure_months = []
    hireability = []

    for item in batch:
        # Pad input sequence
        padded = torch.zeros(max_len, dtype=torch.long)
        padded[:item['length']] = item['input_ids']
        input_ids.append(padded)

        lengths.append(item['length'])
        next_title_ids.append(item['next_title_id'])
        tenure_months.append(item['tenure_months'])
        hireability.append(item['hireability'])

    return {
        'input_ids': torch.stack(input_ids),
        'lengths': torch.tensor(lengths, dtype=torch.long),
        'next_title_ids': torch.tensor(next_title_ids, dtype=torch.long),
        'tenure_months': torch.stack(tenure_months),
        'hireability': torch.stack(hireability)
    }


def create_dataloaders(
    train_sequences: List[Tuple],
    val_sequences: List[Tuple],
    encoder: TitleEncoder,
    batch_size: int = 32
) -> Tuple[DataLoader, DataLoader]:
    """
    Create train and validation dataloaders.

    Args:
        train_sequences: Training sequences
        val_sequences: Validation sequences
        encoder: TitleEncoder instance
        batch_size: Batch size

    Returns:
        (train_loader, val_loader) tuple
    """
    train_dataset = CareerSequenceDataset(train_sequences, encoder)
    val_dataset = CareerSequenceDataset(val_sequences, encoder)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collate_fn,
        num_workers=0  # Avoid multiprocessing issues on macOS
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_fn,
        num_workers=0
    )

    return train_loader, val_loader


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    optimizer: optim.Optimizer,
    device: torch.device
) -> float:
    """
    Train for one epoch.

    Args:
        model: CareerTrajectoryLSTM model
        dataloader: Training dataloader
        optimizer: Optimizer
        device: Device to train on

    Returns:
        Average loss for the epoch
    """
    model.train()
    total_loss = 0.0
    num_batches = 0

    # Loss functions
    ce_loss_fn = nn.CrossEntropyLoss()
    mse_loss_fn = nn.MSELoss()
    bce_loss_fn = nn.BCELoss()

    progress_bar = tqdm(dataloader, desc="Training")

    for batch in progress_bar:
        input_ids = batch['input_ids'].to(device)
        lengths = batch['lengths']
        next_title_ids = batch['next_title_ids'].to(device)
        tenure_months = batch['tenure_months'].to(device)
        hireability = batch['hireability'].to(device)

        # Forward pass
        next_role_logits, tenure_pred, hireability_pred = model(input_ids, lengths)

        # Multi-task loss
        classification_loss = ce_loss_fn(next_role_logits, next_title_ids)
        tenure_loss = mse_loss_fn(tenure_pred, tenure_months)
        hireability_loss = bce_loss_fn(hireability_pred, hireability)

        # Combined loss (weighted)
        loss = classification_loss + 0.1 * tenure_loss + 0.1 * hireability_loss

        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        num_batches += 1

        progress_bar.set_postfix({'loss': loss.item()})

    return total_loss / num_batches


def evaluate(
    model: nn.Module,
    dataloader: DataLoader,
    device: torch.device
) -> Tuple[float, float, np.ndarray, np.ndarray]:
    """
    Evaluate model on validation/test set.

    Args:
        model: CareerTrajectoryLSTM model
        dataloader: Validation/test dataloader
        device: Device to evaluate on

    Returns:
        (accuracy, avg_loss, predictions, labels) tuple
    """
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    all_predictions = []
    all_labels = []

    # Loss functions
    ce_loss_fn = nn.CrossEntropyLoss()
    mse_loss_fn = nn.MSELoss()
    bce_loss_fn = nn.BCELoss()

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            lengths = batch['lengths']
            next_title_ids = batch['next_title_ids'].to(device)
            tenure_months = batch['tenure_months'].to(device)
            hireability = batch['hireability'].to(device)

            # Forward pass
            next_role_logits, tenure_pred, hireability_pred = model(input_ids, lengths)

            # Compute loss
            classification_loss = ce_loss_fn(next_role_logits, next_title_ids)
            tenure_loss = mse_loss_fn(tenure_pred, tenure_months)
            hireability_loss = bce_loss_fn(hireability_pred, hireability)
            loss = classification_loss + 0.1 * tenure_loss + 0.1 * hireability_loss

            total_loss += loss.item()

            # Compute accuracy
            predictions = torch.argmax(next_role_logits, dim=1)
            correct += (predictions == next_title_ids).sum().item()
            total += next_title_ids.size(0)

            # Store for calibration
            probs = torch.softmax(next_role_logits, dim=1)
            max_probs, _ = probs.max(dim=1)
            all_predictions.extend(max_probs.cpu().numpy())
            all_labels.extend((predictions == next_title_ids).cpu().numpy())

    accuracy = correct / total if total > 0 else 0.0
    avg_loss = total_loss / len(dataloader)

    return accuracy, avg_loss, np.array(all_predictions), np.array(all_labels)


def main():
    parser = argparse.ArgumentParser(description='Train career trajectory LSTM model')
    parser.add_argument('--db-url', type=str, help='PostgreSQL connection URL')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--lr', type=float, default=1e-3, help='Learning rate')
    parser.add_argument('--hidden-dim', type=int, default=16, help='LSTM hidden dimension')
    parser.add_argument('--output', type=str, default='models/', help='Output directory')
    parser.add_argument('--patience', type=int, default=5, help='Early stopping patience')
    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load data
    print("\nLoading career sequences...")
    if not args.db_url:
        print("Error: --db-url required")
        return

    df = load_career_sequences(args.db_url)
    train_df, val_df, test_df = temporal_split(df)

    print("\nGenerating sequences...")
    train_sequences = generate_sequences(train_df)
    val_sequences = generate_sequences(val_df)

    # Build vocabulary from training data only
    print("\nBuilding vocabulary...")
    all_train_titles = []
    for input_titles, next_title, _, _ in train_sequences:
        all_train_titles.extend(input_titles)
        all_train_titles.append(next_title)

    encoder = TitleEncoder()
    encoder.fit(all_train_titles)
    encoder.save(output_dir / 'vocab.json')

    # Create dataloaders
    print("\nCreating dataloaders...")
    train_loader, val_loader = create_dataloaders(
        train_sequences, val_sequences, encoder, batch_size=args.batch_size
    )

    # Create model
    print("\nCreating model...")
    model = CareerTrajectoryLSTM(
        vocab_size=encoder.vocab_size,
        hidden_dim=args.hidden_dim
    ).to(device)

    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=args.lr)

    # Training loop with early stopping
    best_val_loss = float('inf')
    patience_counter = 0
    best_model_path = output_dir / 'best.pt'

    print("\nStarting training...")
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}")

        # Train
        train_loss = train_epoch(model, train_loader, optimizer, device)
        print(f"Train loss: {train_loss:.4f}")

        # Validate
        val_accuracy, val_loss, _, _ = evaluate(model, val_loader, device)
        print(f"Val loss: {val_loss:.4f}, Val accuracy: {val_accuracy:.4f}")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Save best model
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_loss,
                'val_accuracy': val_accuracy
            }, best_model_path)
            print(f"Saved best model to {best_model_path}")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"\nEarly stopping after {epoch + 1} epochs")
                break

    print("\nTraining complete!")
    print(f"Best validation loss: {best_val_loss:.4f}")


if __name__ == '__main__':
    main()
