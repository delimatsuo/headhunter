"""
ONNX export for career trajectory LSTM model.
Uses PyTorch 2.5+ dynamo exporter with dynamic shapes for variable sequence lengths.
"""
import argparse
import json
from pathlib import Path
import torch
import onnx
from onnxsim import simplify

from lstm_model import CareerTrajectoryLSTM
from title_encoder import TitleEncoder


def export_to_onnx(
    model_path: str,
    vocab_path: str,
    output_path: str,
    opset_version: int = 17
) -> None:
    """
    Export trained PyTorch model to ONNX format with dynamic shapes.

    Args:
        model_path: Path to trained model checkpoint (.pt file)
        vocab_path: Path to vocabulary JSON file
        output_path: Output path for ONNX model
        opset_version: ONNX opset version (default: 17)
    """
    print(f"Loading model from {model_path}...")

    # Load vocabulary to get vocab_size
    encoder = TitleEncoder()
    encoder.load(vocab_path)

    # Load model checkpoint
    checkpoint = torch.load(model_path, map_location='cpu')

    # Recreate model
    model = CareerTrajectoryLSTM(vocab_size=encoder.vocab_size)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    print("Model loaded successfully")

    # Create example inputs (batch=1, seq_len=10)
    # Actual shapes will be dynamic at inference time
    batch_size = 1
    seq_len = 10
    example_title_ids = torch.randint(0, encoder.vocab_size, (batch_size, seq_len))
    example_lengths = torch.tensor([seq_len])

    print(f"\nExample input shapes:")
    print(f"  title_ids: {example_title_ids.shape}")
    print(f"  lengths: {example_lengths.shape}")

    # Export to ONNX with dynamic shapes
    print(f"\nExporting to ONNX with opset {opset_version}...")

    try:
        # PyTorch 2.5+ dynamo exporter (per RESEARCH.md)
        torch.onnx.export(
            model,
            (example_title_ids, example_lengths),
            output_path,
            dynamo=True,  # CRITICAL: Use dynamo exporter per RESEARCH.md
            input_names=['title_ids', 'lengths'],
            output_names=['next_role_logits', 'tenure_pred', 'hireability'],
            dynamic_shapes={
                'title_ids': {0: torch.export.Dim('batch'), 1: torch.export.Dim('seq_len')},
                'lengths': {0: torch.export.Dim('batch')}
            },
            opset_version=opset_version
        )
        print(f"Model exported to {output_path}")

    except Exception as e:
        print(f"Warning: dynamo export failed ({e}), trying legacy export...")
        # Fallback to legacy export if dynamo fails
        torch.onnx.export(
            model,
            (example_title_ids, example_lengths),
            output_path,
            input_names=['title_ids', 'lengths'],
            output_names=['next_role_logits', 'tenure_pred', 'hireability'],
            dynamic_axes={
                'title_ids': {0: 'batch', 1: 'seq_len'},
                'lengths': {0: 'batch'}
            },
            opset_version=opset_version
        )
        print(f"Model exported to {output_path} (legacy mode)")

    # Verify ONNX model
    print("\nVerifying ONNX model...")
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("ONNX model verified successfully")


def simplify_onnx(model_path: str) -> None:
    """
    Simplify ONNX model for optimization.

    Args:
        model_path: Path to ONNX model to simplify
    """
    print(f"\nSimplifying ONNX model at {model_path}...")

    # Load model
    onnx_model = onnx.load(model_path)

    # Simplify
    try:
        simplified_model, check = simplify(onnx_model)

        if check:
            # Save simplified model
            output_path = model_path.replace('.onnx', '-simplified.onnx')
            onnx.save(simplified_model, output_path)
            print(f"Simplified model saved to {output_path}")

            # Compare file sizes
            import os
            original_size = os.path.getsize(model_path)
            simplified_size = os.path.getsize(output_path)
            reduction = (1 - simplified_size / original_size) * 100

            print(f"Size reduction: {reduction:.1f}%")
            print(f"  Original: {original_size:,} bytes")
            print(f"  Simplified: {simplified_size:,} bytes")
        else:
            print("Simplification failed - model unchanged")

    except Exception as e:
        print(f"Error during simplification: {e}")


def main():
    parser = argparse.ArgumentParser(description='Export trained model to ONNX format')
    parser.add_argument('--checkpoint', type=str, required=True, help='Path to model checkpoint (.pt)')
    parser.add_argument('--vocab', type=str, required=True, help='Path to vocabulary JSON')
    parser.add_argument('--output', type=str, required=True, help='Output ONNX model path')
    parser.add_argument('--simplify', action='store_true', help='Simplify ONNX model after export')
    parser.add_argument('--opset-version', type=int, default=17, help='ONNX opset version')
    args = parser.parse_args()

    # Export model
    export_to_onnx(
        model_path=args.checkpoint,
        vocab_path=args.vocab,
        output_path=args.output,
        opset_version=args.opset_version
    )

    # Optionally simplify
    if args.simplify:
        simplify_onnx(args.output)

    print("\nExport complete!")


if __name__ == '__main__':
    main()
