"""
PyTorch LSTM model for career trajectory prediction.
Based on research showing bidirectional LSTM outperforms GRU for career paths.
"""
import torch
import torch.nn as nn


class CareerTrajectoryLSTM(nn.Module):
    """
    Bidirectional LSTM for career trajectory prediction.

    Based on research showing bidirectional LSTM outperforms attention variants
    for career path prediction (Frontiers in Big Data, 2025).

    Architecture:
    - Embedding layer for job title encoding
    - Bidirectional LSTM (hidden_dim=16 is research-validated)
    - Three output heads:
      1. Next role classifier (multi-class classification)
      2. Tenure predictor (regression for min/max months)
      3. Hireability scorer (binary classification)
    """

    def __init__(
        self,
        vocab_size: int,           # Number of unique job titles
        embedding_dim: int = 128,  # Title embedding dimension
        hidden_dim: int = 16,      # LSTM hidden dimension (research-validated)
        num_layers: int = 2,
        dropout: float = 0.1,
        num_classes: int = None    # For next role classification (defaults to vocab_size)
    ):
        super().__init__()

        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_classes = num_classes or vocab_size

        # Embedding layer (index 0 is padding/unknown)
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)

        # Bidirectional LSTM (research shows this outperforms GRU)
        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,  # CRITICAL: bidirectional per RESEARCH.md
            dropout=dropout if num_layers > 1 else 0
        )

        # Next role classifier head
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),  # *2 for bidirectional
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, self.num_classes)
        )

        # Tenure prediction head (regression for [min_months, max_months])
        self.tenure_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 32),
            nn.ReLU(),
            nn.Linear(32, 2)  # Output: [min_months, max_months]
        )

        # Hireability score head (0-1 probability)
        self.hireability_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, title_ids: torch.Tensor, lengths: torch.Tensor = None):
        """
        Forward pass through the model.

        Args:
            title_ids: (batch, seq_len) tensor of title indices
            lengths: (batch,) tensor of sequence lengths for packing (optional)

        Returns:
            Tuple of (next_role_logits, tenure_pred, hireability):
            - next_role_logits: (batch, num_classes) logits for next role
            - tenure_pred: (batch, 2) predictions for [min_months, max_months]
            - hireability: (batch, 1) probability score
        """
        # Embed title sequences
        embedded = self.embedding(title_ids)  # (batch, seq_len, embedding_dim)

        # Pack sequences if lengths provided (for variable length sequences)
        if lengths is not None:
            # Pack for efficient processing
            packed = nn.utils.rnn.pack_padded_sequence(
                embedded, lengths.cpu(), batch_first=True, enforce_sorted=False
            )
            lstm_out, (hidden, cell) = self.lstm(packed)
            # Unpack for downstream processing
            lstm_out, _ = nn.utils.rnn.pad_packed_sequence(lstm_out, batch_first=True)
        else:
            lstm_out, (hidden, cell) = self.lstm(embedded)

        # Use final hidden state (concatenate forward and backward)
        # hidden shape: (num_layers * 2, batch, hidden_dim)
        # -2 is the last layer forward, -1 is the last layer backward
        final_forward = hidden[-2, :, :]   # (batch, hidden_dim)
        final_backward = hidden[-1, :, :]  # (batch, hidden_dim)
        combined = torch.cat([final_forward, final_backward], dim=1)  # (batch, hidden_dim * 2)

        # Pass through output heads
        next_role_logits = self.classifier(combined)      # (batch, num_classes)
        tenure_pred = self.tenure_head(combined)          # (batch, 2)
        hireability = self.hireability_head(combined)     # (batch, 1)

        return next_role_logits, tenure_pred, hireability


if __name__ == '__main__':
    """Test model instantiation and forward pass"""
    print("Testing CareerTrajectoryLSTM...")

    # Create model
    vocab_size = 1000
    model = CareerTrajectoryLSTM(vocab_size=vocab_size)

    print(f"\nModel architecture:")
    print(model)

    # Test forward pass
    batch_size = 4
    seq_len = 10
    title_ids = torch.randint(0, vocab_size, (batch_size, seq_len))
    lengths = torch.tensor([10, 8, 6, 5])  # Variable lengths

    print(f"\nInput shape: {title_ids.shape}")
    print(f"Lengths: {lengths}")

    # Forward pass
    next_role_logits, tenure_pred, hireability = model(title_ids, lengths)

    print(f"\nOutput shapes:")
    print(f"  Next role logits: {next_role_logits.shape}")
    print(f"  Tenure prediction: {tenure_pred.shape}")
    print(f"  Hireability: {hireability.shape}")

    print("\nModel test passed!")
