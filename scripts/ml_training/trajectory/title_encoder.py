"""
Title encoder for career trajectory model.
Normalizes and encodes job titles into integer indices for LSTM input.
"""
import json
import re
from typing import List, Dict


class TitleEncoder:
    """
    Encode job titles to integer indices for model training.

    Features:
    - Lowercase normalization
    - Punctuation removal
    - Common abbreviation mapping (Sr. -> Senior, Jr. -> Junior)
    - Index 0 reserved for unknown/padding
    """

    def __init__(self):
        self.title_to_idx: Dict[str, int] = {}
        self.idx_to_title: Dict[int, str] = {}
        self.vocab_size = 0

        # Common abbreviation mappings
        self.abbreviations = {
            'sr.': 'senior',
            'sr': 'senior',
            'jr.': 'junior',
            'jr': 'junior',
            'mgr': 'manager',
            'mgr.': 'manager',
            'eng': 'engineer',
            'eng.': 'engineer',
            'dev': 'developer',
            'swe': 'software engineer',
            'pm': 'product manager',
            'vp': 'vice president',
            'cto': 'chief technology officer',
            'ceo': 'chief executive officer',
            'cfo': 'chief financial officer',
            'coo': 'chief operating officer',
        }

    def normalize_title(self, title: str) -> str:
        """
        Normalize title string for consistent encoding.

        Args:
            title: Raw job title

        Returns:
            Normalized title string
        """
        # Lowercase
        title = title.lower().strip()

        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title)

        # Remove punctuation except periods (for abbreviations)
        title = re.sub(r'[^\w\s.]', '', title)

        # Replace abbreviations
        words = title.split()
        normalized_words = []
        for word in words:
            # Check if word (with or without period) is an abbreviation
            word_clean = word.rstrip('.')
            if word_clean in self.abbreviations:
                normalized_words.append(self.abbreviations[word_clean])
            elif word in self.abbreviations:
                normalized_words.append(self.abbreviations[word])
            else:
                normalized_words.append(word)

        title = ' '.join(normalized_words)

        # Remove any remaining periods
        title = title.replace('.', '')

        return title

    def fit(self, titles: List[str]) -> None:
        """
        Build vocabulary from list of titles.

        Args:
            titles: List of job title strings
        """
        # Normalize all titles
        normalized_titles = [self.normalize_title(t) for t in titles]

        # Get unique titles
        unique_titles = sorted(set(normalized_titles))

        # Build mappings (index 0 reserved for unknown/padding)
        self.title_to_idx = {'<UNK>': 0}
        self.idx_to_title = {0: '<UNK>'}

        for idx, title in enumerate(unique_titles, start=1):
            if title and title != '<unk>':  # Skip empty and duplicate unknown
                self.title_to_idx[title] = idx
                self.idx_to_title[idx] = title

        self.vocab_size = len(self.title_to_idx)
        print(f"Built vocabulary with {self.vocab_size} unique titles")

    def encode(self, title: str) -> int:
        """
        Encode title to integer index.

        Args:
            title: Job title string

        Returns:
            Integer index (0 if unknown)
        """
        normalized = self.normalize_title(title)
        return self.title_to_idx.get(normalized, 0)  # 0 for unknown

    def decode(self, index: int) -> str:
        """
        Decode integer index to title string.

        Args:
            index: Integer index

        Returns:
            Title string ('<UNK>' if index not found)
        """
        return self.idx_to_title.get(index, '<UNK>')

    def encode_sequence(self, titles: List[str]) -> List[int]:
        """
        Encode sequence of titles.

        Args:
            titles: List of title strings

        Returns:
            List of integer indices
        """
        return [self.encode(t) for t in titles]

    def decode_sequence(self, indices: List[int]) -> List[str]:
        """
        Decode sequence of indices.

        Args:
            indices: List of integer indices

        Returns:
            List of title strings
        """
        return [self.decode(i) for i in indices]

    def save(self, path: str) -> None:
        """
        Save vocabulary to JSON file.

        Args:
            path: Output file path
        """
        vocab_data = {
            'title_to_idx': self.title_to_idx,
            'idx_to_title': {str(k): v for k, v in self.idx_to_title.items()},  # JSON keys must be strings
            'vocab_size': self.vocab_size
        }
        with open(path, 'w') as f:
            json.dump(vocab_data, f, indent=2)
        print(f"Saved vocabulary to {path}")

    def load(self, path: str) -> None:
        """
        Load vocabulary from JSON file.

        Args:
            path: Input file path
        """
        with open(path, 'r') as f:
            vocab_data = json.load(f)

        self.title_to_idx = vocab_data['title_to_idx']
        self.idx_to_title = {int(k): v for k, v in vocab_data['idx_to_title'].items()}  # Convert back to int keys
        self.vocab_size = vocab_data['vocab_size']
        print(f"Loaded vocabulary with {self.vocab_size} titles from {path}")


if __name__ == '__main__':
    """Example usage for testing"""
    # Test encoder
    encoder = TitleEncoder()

    test_titles = [
        'Software Engineer',
        'Sr. Software Engineer',
        'Senior Software Engineer',
        'Staff Engineer',
        'Principal Engineer',
        'Engineering Manager',
        'Sr. Engineering Manager',
        'Director of Engineering',
        'VP of Engineering',
        'CTO'
    ]

    print("Fitting encoder on test titles...")
    encoder.fit(test_titles)

    print("\nTesting encoding:")
    for title in ['Software Engineer', 'senior software engineer', 'Sr. Software Engineer']:
        idx = encoder.encode(title)
        decoded = encoder.decode(idx)
        print(f"  '{title}' -> {idx} -> '{decoded}'")

    print("\nTesting unknown title:")
    idx = encoder.encode('Unknown Job Title')
    print(f"  'Unknown Job Title' -> {idx} (should be 0)")

    print("\nTesting sequence encoding:")
    sequence = ['Software Engineer', 'Sr. Software Engineer', 'Staff Engineer']
    encoded = encoder.encode_sequence(sequence)
    decoded = encoder.decode_sequence(encoded)
    print(f"  Input: {sequence}")
    print(f"  Encoded: {encoded}")
    print(f"  Decoded: {decoded}")
