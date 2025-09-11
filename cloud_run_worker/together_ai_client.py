"""
Together AI client for candidate enrichment
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from .config import Config
from .models import TogetherAIRequest, TogetherAIResponse

logger = logging.getLogger(__name__)


class TogetherAIClient:
    """Client for Together AI API integration"""
    
    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.together_ai_api_key
        self.base_url = config.together_ai_base_url
        self.model = config.together_ai_model
        self.timeout = config.together_ai_timeout
        self.max_retries = config.together_ai_max_retries
        
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def initialize(self):
        """Initialize HTTP session"""
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Headhunter-Worker/1.0"
            }
        )
        
        logger.info("Together AI client initialized")
    
    async def shutdown(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            logger.info("Together AI client shutdown complete")
    
    async def enrich_candidate(self, candidate_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich candidate data using Together AI
        
        Args:
            candidate_data: Raw candidate information
            
        Returns:
            Dict[str, Any]: Enriched candidate profile
        """
        try:
            start_time = datetime.now()
            
            # Prepare prompt for candidate enrichment
            prompt = self._build_enrichment_prompt(candidate_data)
            
            # Create API request
            request_data = TogetherAIRequest(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                model=self.model,
                max_tokens=2048,
                temperature=0.1,
                top_p=0.9,
                stream=False
            )
            
            # Make API call with retry logic
            response = await self._make_api_call(request_data)
            
            # Parse and validate response
            enriched_data = self._parse_response(response)
            
            # Add processing metadata
            processing_time = (datetime.now() - start_time).total_seconds()
            enriched_data["processing_time"] = processing_time
            enriched_data["token_usage"] = response.usage
            
            logger.info(f"Successfully enriched candidate in {processing_time:.2f}s")
            return enriched_data
            
        except Exception as e:
            logger.error(f"Failed to enrich candidate: {e}")
            raise Exception(f"Together AI API error: {e}")
    
    def _build_enrichment_prompt(self, candidate_data: Dict[str, Any]) -> str:
        """Build enrichment prompt from candidate data"""
        
        name = candidate_data.get("name", "Unknown")
        resume_text = candidate_data.get("resume_text", "")
        recruiter_comments = candidate_data.get("recruiter_comments", "")
        
        prompt = f"""
Analyze the following candidate profile and provide comprehensive enrichment:

**Candidate Name:** {name}

**Resume/Profile Text:**
{resume_text}

**Recruiter Comments:**
{recruiter_comments}

Please provide a detailed analysis in the following JSON format:

{{
    "resume_analysis": {{
        "career_trajectory": {{
            "current_level": "Junior|Mid|Senior|Staff|Principal|VP|C-Level",
            "progression_speed": "Slow|Moderate|Fast|Rapid",
            "trajectory_type": "Individual Contributor|Technical Leadership|People Management|Executive",
            "years_experience": <number>,
            "career_changes": <number>,
            "domain_expertise": ["domain1", "domain2"]
        }},
        "technical_skills": ["skill1", "skill2", "skill3"],
        "soft_skills": ["skill1", "skill2", "skill3"],
        "leadership_scope": {{
            "has_leadership": true|false,
            "team_size": <number>,
            "leadership_level": "Team Lead|Manager|Director|VP",
            "leadership_style": ["style1", "style2"]
        }},
        "company_pedigree": {{
            "tier_level": "Tier1|Tier2|Tier3|Startup",
            "company_types": ["Big Tech", "Startup", "Enterprise"],
            "recent_companies": ["company1", "company2"],
            "brand_recognition": "High|Medium|Low"
        }},
        "education": {{
            "highest_degree": "PhD|MS|BS|Associates|High School",
            "institutions": ["school1", "school2"],
            "fields_of_study": ["field1", "field2"]
        }}
    }},
    "recruiter_insights": {{
        "sentiment": "positive|neutral|negative", 
        "strengths": ["strength1", "strength2"],
        "concerns": ["concern1", "concern2"],
        "red_flags": ["flag1", "flag2"],
        "cultural_fit": {{
            "cultural_alignment": "excellent|good|fair|poor",
            "work_style": ["style1", "style2"],
            "values_alignment": ["value1", "value2"]
        }},
        "recommendation": "strong_hire|hire|maybe|pass|strong_pass",
        "key_themes": ["theme1", "theme2"]
    }},
    "overall_score": <float between 0.0 and 1.0>
}}

Ensure all responses are in valid JSON format with realistic, professional assessments.
"""
        return prompt
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for candidate enrichment"""
        return """
You are an expert AI recruiter and talent analyst specializing in technical roles. 
Your task is to analyze candidate profiles and provide comprehensive, objective assessments.

Guidelines:
- Be thorough but concise in your analysis
- Focus on factual observations from the provided data
- Provide realistic scoring and assessments
- Always return valid JSON format
- Consider both technical and cultural fit aspects
- Be objective and professional in tone
- If information is missing, indicate as "Not specified" rather than guessing
"""
    
    async def _make_api_call(self, request_data: TogetherAIRequest) -> TogetherAIResponse:
        """Make API call to Together AI with retry logic"""
        
        if not self.session:
            raise Exception("Session not initialized")
        
        url = f"{self.base_url}/chat/completions"
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.session.post(url, json=request_data.dict()) as response:
                    
                    # Handle rate limiting
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 1))
                        if attempt < self.max_retries:
                            logger.warning(f"Rate limited, retrying in {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            raise Exception("Rate limit exceeded, max retries reached")
                    
                    # Handle other HTTP errors
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")
                    
                    # Parse successful response
                    response_data = await response.json()
                    
                    return TogetherAIResponse(
                        choices=response_data.get("choices", []),
                        usage=response_data.get("usage", {}),
                        model=response_data.get("model", self.model),
                        created=response_data.get("created", 0)
                    )
                    
            except asyncio.TimeoutError:
                if attempt < self.max_retries:
                    delay = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Timeout on attempt {attempt + 1}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise Exception("Request timeout, max retries reached")
            
            except Exception as e:
                if attempt < self.max_retries:
                    delay = 2 ** attempt
                    logger.warning(f"Request failed on attempt {attempt + 1}, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    raise
        
        raise Exception("Max retries exceeded")
    
    def _parse_response(self, response: TogetherAIResponse) -> Dict[str, Any]:
        """Parse and validate Together AI response"""
        
        try:
            if not response.choices:
                raise Exception("No choices in response")
            
            # Extract content from first choice
            choice = response.choices[0]
            content = choice.get("message", {}).get("content", "")
            
            if not content:
                raise Exception("Empty content in response")
            
            # Parse JSON content
            try:
                enriched_data = json.loads(content)
            except json.JSONDecodeError as e:
                # Try to clean up common JSON issues
                cleaned_content = self._clean_json_response(content)
                try:
                    enriched_data = json.loads(cleaned_content)
                except json.JSONDecodeError:
                    raise Exception(f"Invalid JSON in response: {e}")
            
            # Validate required fields
            required_fields = ["resume_analysis", "recruiter_insights", "overall_score"]
            for field in required_fields:
                if field not in enriched_data:
                    raise Exception(f"Missing required field in response: {field}")
            
            # Validate overall_score
            score = enriched_data.get("overall_score", 0)
            if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                enriched_data["overall_score"] = 0.5  # Default score
            
            return enriched_data
            
        except Exception as e:
            logger.error(f"Failed to parse Together AI response: {e}")
            raise Exception(f"Response parsing error: {e}")
    
    def _clean_json_response(self, content: str) -> str:
        """Clean up common JSON formatting issues in AI responses"""
        
        # Remove markdown code blocks
        content = content.replace("```json", "").replace("```", "")
        
        # Remove leading/trailing whitespace
        content = content.strip()
        
        # Find JSON object boundaries
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        
        if start_idx != -1 and end_idx > start_idx:
            content = content[start_idx:end_idx]
        
        return content
    
    async def health_check(self) -> bool:
        """Perform health check on Together AI API"""
        
        try:
            if not self.session:
                return False
            
            # Simple test request
            test_data = TogetherAIRequest(
                messages=[{"role": "user", "content": "Hello"}],
                model=self.model,
                max_tokens=10
            )
            
            url = f"{self.base_url}/chat/completions"
            
            async with self.session.post(url, json=test_data.dict()) as response:
                return response.status == 200
                
        except Exception as e:
            logger.warning(f"Together AI health check failed: {e}")
            return False