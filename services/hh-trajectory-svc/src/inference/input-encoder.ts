/**
 * Input encoder for converting job title sequences to ONNX model inputs.
 * Mirrors the Python TitleEncoder from ml_training/trajectory/title_encoder.py
 */
import * as fs from 'fs';

export interface VocabularyData {
  title_to_idx: Record<string, number>;
  idx_to_title: Record<string, string>;
  vocab_size: number;
}

export class InputEncoder {
  private titleToIdx: Map<string, number>;
  private idxToTitle: Map<number, string>;
  private vocabSize: number;

  // Common abbreviation mappings (matches Python implementation)
  private readonly abbreviations: Record<string, string> = {
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
  };

  constructor(vocabPath: string) {
    this.titleToIdx = new Map();
    this.idxToTitle = new Map();
    this.vocabSize = 0;

    this.loadVocabulary(vocabPath);
  }

  /**
   * Load vocabulary from JSON file.
   *
   * @param vocabPath - Path to vocabulary JSON file
   */
  private loadVocabulary(vocabPath: string): void {
    console.log(`[InputEncoder] Loading vocabulary from ${vocabPath}...`);

    const data = fs.readFileSync(vocabPath, 'utf-8');
    const vocab: VocabularyData = JSON.parse(data);

    // Build maps
    for (const [title, idx] of Object.entries(vocab.title_to_idx)) {
      this.titleToIdx.set(title, idx);
    }

    for (const [idxStr, title] of Object.entries(vocab.idx_to_title)) {
      this.idxToTitle.set(parseInt(idxStr, 10), title);
    }

    this.vocabSize = vocab.vocab_size;

    console.log(`[InputEncoder] Loaded vocabulary with ${this.vocabSize} titles`);
  }

  /**
   * Normalize title string for consistent encoding.
   * Matches Python TitleEncoder.normalize_title() logic.
   *
   * @param title - Raw job title
   * @returns Normalized title string
   */
  private normalizeTitle(title: string): string {
    // Lowercase and trim
    let normalized = title.toLowerCase().trim();

    // Remove extra whitespace
    normalized = normalized.replace(/\s+/g, ' ');

    // Remove punctuation except periods (for abbreviations)
    normalized = normalized.replace(/[^\w\s.]/g, '');

    // Replace abbreviations
    const words = normalized.split(' ');
    const normalizedWords: string[] = [];

    for (const word of words) {
      // Check if word (with or without period) is an abbreviation
      const wordClean = word.replace(/\.$/, '');
      if (this.abbreviations[wordClean]) {
        normalizedWords.push(this.abbreviations[wordClean]);
      } else if (this.abbreviations[word]) {
        normalizedWords.push(this.abbreviations[word]);
      } else {
        normalizedWords.push(word);
      }
    }

    normalized = normalizedWords.join(' ');

    // Remove any remaining periods
    normalized = normalized.replace(/\./g, '');

    return normalized;
  }

  /**
   * Encode single title to integer index.
   *
   * @param title - Job title string
   * @returns Integer index (0 if unknown)
   */
  encodeTitle(title: string): number {
    const normalized = this.normalizeTitle(title);
    return this.titleToIdx.get(normalized) ?? 0; // 0 for unknown/padding
  }

  /**
   * Encode sequence of titles to BigInt64Array for ONNX tensor.
   *
   * @param titles - Array of job title strings
   * @returns BigInt64Array of encoded indices
   */
  encode(titles: string[]): BigInt64Array {
    const encoded = new BigInt64Array(titles.length);
    for (let i = 0; i < titles.length; i++) {
      encoded[i] = BigInt(this.encodeTitle(titles[i]));
    }
    return encoded;
  }

  /**
   * Decode integer index to title string.
   *
   * @param index - Integer index
   * @returns Title string ('<UNK>' if not found)
   */
  decode(index: number): string {
    return this.idxToTitle.get(index) ?? '<UNK>';
  }

  /**
   * Get vocabulary size.
   *
   * @returns Number of unique titles in vocabulary
   */
  getVocabSize(): number {
    return this.vocabSize;
  }
}
