# Quality Validation System

## Overview

The Quality Validation System ensures the reliability and accuracy of LLM-generated outputs in the Headhunter AI system. It provides comprehensive validation, quality scoring, and automatic correction mechanisms for both resume analysis and recruiter insights.

## Features

### 1. JSON Schema Validation
- **Resume Analysis**: Validates career trajectory, leadership scope, company pedigree, technical skills, education, and cultural signals
- **Recruiter Insights**: Validates sentiment, strengths, concerns, cultural fit assessments, and recommendations
- **Automatic Type Checking**: Ensures data types match expected schemas
- **Enum Validation**: Validates against predefined value sets (e.g., recommendation levels, sentiment types)

### 2. Quality Metrics
- **Completeness Score**: Measures how much of the expected data is present
- **Consistency Score**: Checks for logical consistency between related fields
- **Content Quality Score**: Evaluates the quality of text content and data values
- **Schema Compliance Score**: Measures adherence to expected data structure
- **Overall Quality Score**: Weighted combination of all metrics

### 3. Fallback Correction Mechanisms
- **Type Conversion**: Automatically converts compatible data types (e.g., "5" → 5)
- **Array Normalization**: Converts comma-separated strings to arrays
- **Default Value Insertion**: Provides sensible defaults for missing critical fields
- **Enum Correction**: Maps similar values to valid enum options
- **Data Cleaning**: Removes invalid or empty entries

### 4. Integration with LLM Processor
- **Seamless Integration**: Automatically validates all LLM outputs during processing
- **Quality Reporting**: Tracks validation metrics for each processed candidate
- **Automatic Correction**: Applies fallback corrections when validation fails
- **Performance Monitoring**: Logs validation results and processing times

## Architecture

### Core Components

#### `LLMOutputValidator`
Main validation orchestrator that coordinates all validation tasks.

```python
from quality_validator import LLMOutputValidator

validator = LLMOutputValidator()
result = validator.validate_llm_output(data, "resume", apply_fallbacks=True)
```

#### `ValidationResult`
Contains validation outcomes and quality metrics.

```python
@dataclass
class ValidationResult:
    is_valid: bool
    quality_score: float
    errors: List[str]
    validated_data: Optional[Dict]
    fallback_applied: bool
    metrics: Optional[QualityMetrics]
```

#### `QualityMetrics`
Detailed quality scoring breakdown.

```python
@dataclass
class QualityMetrics:
    completeness_score: float
    consistency_score: float
    content_quality_score: float
    schema_compliance_score: float
    overall_score: float
```

### JSON Schemas

#### Resume Analysis Schema
```json
{
  "career_trajectory": {
    "current_level": "Entry|Mid|Senior|Lead|Executive",
    "progression_speed": "Fast|Moderate|Slow",
    "trajectory_type": "string",
    "career_changes": "integer",
    "domain_expertise": ["string"]
  },
  "leadership_scope": {
    "has_leadership": "boolean",
    "team_size": "integer",
    "leadership_level": "string",
    "leadership_style": ["string"],
    "mentorship_experience": "boolean"
  },
  "company_pedigree": {
    "tier_level": "Tier1|Tier2|Tier3|Startup",
    "company_types": ["string"],
    "brand_recognition": "High|Medium|Low",
    "recent_companies": ["string"]
  },
  "years_experience": "integer",
  "technical_skills": ["string"],
  "soft_skills": ["string"],
  "education": {
    "highest_degree": "string",
    "institutions": ["string"],
    "fields_of_study": ["string"]
  },
  "cultural_signals": ["string"]
}
```

#### Recruiter Insights Schema
```json
{
  "sentiment": "positive|neutral|negative|mixed",
  "strengths": ["string"],
  "concerns": ["string"],
  "red_flags": ["string"],
  "leadership_indicators": ["string"],
  "cultural_fit": {
    "cultural_alignment": "excellent|good|fair|poor",
    "work_style": ["string"],
    "values_alignment": ["string"],
    "team_fit": "excellent|good|fair|poor",
    "communication_style": "string",
    "adaptability": "high|medium|low",
    "cultural_add": ["string"]
  },
  "recommendation": "strong_hire|hire|maybe|no_hire",
  "readiness_level": "ready_now|needs_training|long_term",
  "key_themes": ["string"],
  "development_areas": ["string"],
  "competitive_advantages": ["string"]
}
```

## Quality Scoring Algorithm

### Completeness Score (0.0 - 1.0)
- Calculates the percentage of expected fields that are present and non-empty
- Weights required fields more heavily than optional fields
- Penalizes completely missing sections more than partially complete ones

### Consistency Score (0.0 - 1.0)
- Checks logical relationships between fields
- Examples:
  - Leadership role with appropriate years of experience
  - Company tier alignment with brand recognition
  - Career level consistency with progression speed

### Content Quality Score (0.0 - 1.0)
- Evaluates the quality of text content and data values
- Checks for:
  - Non-empty strings in text fields
  - Reasonable numeric values
  - Proper array structures
  - Valid enum selections

### Schema Compliance Score (0.0 - 1.0)
- Measures adherence to expected JSON schema structure
- Perfect score (1.0) for schema-compliant data
- Proportional scoring based on number of schema violations

### Overall Quality Score
Weighted average of all component scores:
- Completeness: 30%
- Consistency: 25%
- Content Quality: 25%
- Schema Compliance: 20%

## Usage Examples

### Basic Validation
```python
from quality_validator import LLMOutputValidator

validator = LLMOutputValidator()

# Validate resume analysis
resume_data = {...}  # Resume analysis data
result = validator.validate_resume_analysis(resume_data)

print(f"Valid: {result.is_valid}")
print(f"Quality Score: {result.quality_score}")
print(f"Errors: {result.errors}")
```

### Validation with Fallbacks
```python
# Enable automatic correction of common issues
result = validator.validate_llm_output(
    data=problematic_data,
    schema_type="recruiter",
    apply_fallbacks=True
)

if result.fallback_applied:
    print("Corrections were applied")
    corrected_data = result.validated_data
```

### Integration with LLM Processor
The validation system is automatically integrated into the `LLMProcessor`:

```python
from llm_processor import LLMProcessor

processor = LLMProcessor()
profiles, stats = processor.process_batch("candidates.csv")

# Validation results are included in each profile
for profile in profiles:
    if profile.resume_validation:
        print(f"Resume Quality: {profile.resume_validation.quality_score}")
    if profile.recruiter_validation:
        print(f"Recruiter Quality: {profile.recruiter_validation.quality_score}")
```

## Configuration

### Logging
The validator uses Python's logging module. Set the log level during initialization:

```python
validator = LLMOutputValidator(log_level="DEBUG")
```

### Quality Thresholds
Quality thresholds can be customized by modifying the scoring algorithms in the `quality_validator.py` file.

### Schema Customization
JSON schemas are defined as class constants in `LLMOutputValidator`. Modify these to add new fields or change validation rules.

## Performance Considerations

- **Validation Overhead**: ~10-50ms per validation depending on data size
- **Memory Usage**: Minimal additional memory footprint
- **Caching**: Schema compilation is cached for performance
- **Parallel Processing**: Thread-safe for concurrent validation

## Testing

### Unit Tests
```bash
python tests/test_quality_validator.py
```

### Integration Tests
```bash
python tests/test_integration.py
```

### CLI Testing
```bash
# Test with sample data
python scripts/quality_validator.py sample_resume.json resume

# Validate recruiter insights
python scripts/quality_validator.py sample_recruiter.json recruiter --fallbacks
```

## Error Handling

The system provides comprehensive error handling:

1. **Schema Validation Errors**: Clear messages about which fields fail validation
2. **Type Conversion Errors**: Automatic fallback with logging
3. **Missing Data**: Graceful handling with default values
4. **Malformed JSON**: Proper error reporting

## Monitoring and Metrics

### Quality Metrics Tracking
```python
# Extract detailed metrics
metrics = result.metrics
print(f"Completeness: {metrics.completeness_score}")
print(f"Consistency: {metrics.consistency_score}")
print(f"Content Quality: {metrics.content_quality_score}")
print(f"Schema Compliance: {metrics.schema_compliance_score}")
```

### Batch Processing Metrics
The LLM processor automatically tracks validation statistics across batches:

```python
profiles, stats = processor.process_batch(data)
# stats includes overall validation success rates and quality distributions
```

## Future Enhancements

1. **Machine Learning Quality Models**: Train models to predict quality based on text patterns
2. **Dynamic Schema Updates**: Support for runtime schema modifications
3. **Quality Trend Analysis**: Track quality improvements over time
4. **Custom Validation Rules**: User-defined validation logic
5. **Integration with External Systems**: Quality reporting to monitoring dashboards

## Troubleshooting

### Common Issues

**Low Quality Scores**
- Check for missing required fields
- Verify data types match schema expectations
- Review enum values for typos

**Validation Failures**
- Enable DEBUG logging to see detailed error messages
- Use fallback corrections to automatically fix common issues
- Check for malformed JSON or unexpected data structures

**Performance Issues**
- Reduce batch sizes for memory-constrained environments
- Disable detailed metrics calculation if not needed
- Use streaming validation for large datasets

### Support
For issues related to the quality validation system:
1. Check logs for detailed error messages
2. Run unit tests to verify system integrity
3. Use CLI tools for debugging specific data issues
4. Review schema definitions for compatibility requirements