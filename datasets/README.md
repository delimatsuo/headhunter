# Local Dataset Assets

This folder provides a minimal dataset that scripts can use without relying on developer-specific paths or network-mounted storage. It mirrors the structure expected by the batch processing utilities while keeping the footprint small for local testing.

## Structure

```
datasets/
├── csv/
│   └── sample_candidates.csv    # Small candidate dataset referencing resume files
└── resumes/
    ├── emily_watson_resume.txt
    ├── james_thompson_resume.pdf
    ├── john_smith_resume.png
    ├── lisa_park_resume.docx
    ├── marcus_rodriguez_resume.txt
    └── sarah_chen_resume.txt
```

- The CSV uses relative paths (`datasets/resumes/...`) so scripts can resolve resume assets without extra configuration.
- Files cover multiple formats (TXT, PDF, DOCX, PNG) for exercising the extraction code paths.

## Usage

Scripts that previously assumed `/Users/.../CSV files` can now point to this directory:

```bash
export HEADHUNTER_DATASET_DIR="$(pwd)/datasets"
python scripts/process_all_candidates_with_llm.py --help
```

When the `HEADHUNTER_DATASET_DIR` environment variable is set, updated scripts resolve both the CSV input and resume assets from here. If the variable is unset, they fall back to the legacy `CSV files/` layout.

## Source

Resume fixtures are copied from `tests/sample_resumes/` so they stay in sync with the test suite and avoid introducing new proprietary content.
