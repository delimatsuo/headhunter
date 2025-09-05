# Headhunter - AI-Powered Recruitment Analytics

An intelligent system for analyzing recruitment data using local LLMs to extract insights from unstructured candidate information.

## Features

- Local LLM processing using Ollama and Llama 3.1 8b
- Resume analysis and career trajectory insights
- Recruiter comment synthesis
- Pattern recognition across candidate profiles

## Prerequisites

- macOS (tested on Darwin 24.6.0)
- Python 3.x
- Ollama installed locally
- At least 5GB free disk space for Llama 3.1 8b model

## Installation

### 1. Ollama Setup

Ollama is already installed on this system. To install on a new system:

```bash
# macOS
brew install ollama

# Or download from https://ollama.ai
```

### 2. Llama 3.1 8b Model

Pull the Llama 3.1 8b model (4.9 GB):

```bash
ollama pull llama3.1:8b
```

Verify installation:

```bash
ollama list
# Should show: llama3.1:8b with size ~4.9 GB
```

### 3. Test Model

```bash
ollama run llama3.1:8b "Hello, are you working?"
```

## Testing

Run the test suite to verify Ollama setup:

```bash
python3 tests/test_ollama_setup.py
```

Tests include:
- Ollama installation verification
- Model availability check
- Integration test with model response
- API endpoint accessibility
- Performance benchmarks

## Project Structure

```
headhunter/
├── .taskmaster/         # Task management system
│   ├── tasks/          # Task definitions
│   └── docs/           # PRD and documentation
├── tests/              # Test suites
│   └── test_ollama_setup.py
├── scripts/            # Utility scripts
├── CSV files/          # Data directory
└── README.md           # This file
```

## Development Workflow

This project uses Task Master for task management:

```bash
# View next task
task-master next

# List all tasks
task-master list

# Mark task complete
task-master set-status --id=<task-id> --status=done
```

## Task Completion Protocol

For each completed task:
1. Run unit and integration tests
2. Update documentation
3. Commit changes with descriptive message
4. Push to remote repository
5. Move to next task

## Current Status

- ✅ Task #1: Ollama with Llama 3.1 8b setup complete
- ⏳ Task #2: Create LLM prompts for resume analysis (next)

## API Usage

Ollama provides a REST API at `http://localhost:11434`:

```bash
# Check API version
curl http://localhost:11434/api/version

# Generate completion
curl -X POST http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Analyze this resume..."
}'
```

## Performance

- Model load time: < 1 second (after initial load)
- Response generation: ~50-100 tokens/second
- Memory usage: ~5-6 GB when model is loaded

## License

[Your License Here]

## Contact

[Your Contact Information]