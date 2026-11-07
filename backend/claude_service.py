
import json
import logging
import re
import boto3

from anthropic import Anthropic
from config import CLAUDE_SECRET_NAME, CLAUDE_MODEL

logger = logging.getLogger(__name__)

secrets = boto3.client("secretsmanager")


def get_api_key() -> str:
    result = secrets.get_secret_value(SecretId=CLAUDE_SECRET_NAME)
    secret = result.get("SecretString", "")

    try:
        parsed = json.loads(secret)
        return (
            parsed.get("CLAUDE_API_KEY")
            or parsed.get("api_key")
            or secret
        )
    except json.JSONDecodeError:
        return secret


def extract_json(raw: str) -> dict:
    """
    Extract JSON even if Claude surrounds it with
    Markdown code fences or explanatory text.
    """

    cleaned = raw.strip()

    # Remove Markdown JSON code fences.
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    # First try parsing the entire response.
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find a valid JSON object within surrounding text.
    decoder = json.JSONDecoder()

    for index, character in enumerate(cleaned):
        if character == "{":
            try:
                result, _ = decoder.raw_decode(cleaned[index:])
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                continue

    raise ValueError("Claude did not return a valid JSON object.")


def analyze_with_claude(
    resume_text: str,
    job_description: str,
    skill_result: dict
) -> dict:

    client = Anthropic(api_key=get_api_key())

    prompt = f"""
You are an experienced technical recruiter and professional
resume evaluator.

Your task is to evaluate a candidate's resume against a
specific job description.

Perform a detailed, evidence-based assessment.

IMPORTANT EVALUATION RULES:

1. Analyze the resume only using information explicitly
   provided in the resume.

2. Compare the candidate's technical skills against the
   job description.

3. Clearly identify:
   - Skills present in both the resume and job description.
   - Skills required by the job but missing from the resume.
   - Skills that are related but not equivalent.

4. Do not assume that knowing one framework means knowing
   another framework.

5. Evaluate relevant work experience, projects, education,
   technical knowledge and responsibilities.

6. Identify strengths that make the candidate suitable
   for the position.

7. Identify genuine gaps and areas requiring improvement.

8. Provide practical recommendations to improve the
   candidate's suitability.

9. Do not invent certifications, projects, experience,
   achievements or technical skills.

10. Calculate a suitability score from 0 to 100.
    Consider skills, experience, projects and relevance
    to the job description.

11. Distinguish between an explicitly missing skill and
    a skill for which the resume provides insufficient
    evidence.

OUTPUT REQUIREMENTS:

Return ONLY one valid JSON object.

Do not include:
- Markdown formatting
- Markdown code fences
- Introductory text
- Explanations outside JSON

Use exactly this JSON structure:

{{
    "overall_assessment": "Detailed candidate assessment",
    "strengths": [
        "Strength with evidence from resume"
    ],
    "gaps": [
        "Missing requirement and explanation"
    ],
    "recommendations": [
        "Actionable recommendation"
    ],
    "matched_skills": [
        "Skill found in both resume and job description"
    ],
    "missing_skills": [
        "Skill required by job but not found in resume"
    ],
    "experience_assessment": "Assessment of relevant experience",
    "project_assessment": "Assessment of relevant projects",
    "suitability_score": 0
}}

The suitability_score must be an integer between 0 and 100.

RESUME:
{resume_text[:18000]}

JOB DESCRIPTION:
{job_description[:12000]}

EXISTING SKILL COMPARISON:
{json.dumps(skill_result, ensure_ascii=False)}
"""

    logger.info("Calling Claude API model=%s", CLAUDE_MODEL)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    raw = "".join(
        block.text
        for block in response.content
        if getattr(block, "type", "") == "text"
    )

    logger.info(
        "Claude response received stop_reason=%s response_length=%s",
        response.stop_reason,
        len(raw)
    )

    if response.stop_reason == "max_tokens":
        raise ValueError(
            "Claude response was truncated. Increase max_tokens."
        )

    result = extract_json(raw)

    required_keys = [
        "overall_assessment",
        "strengths",
        "gaps",
        "recommendations",
        "matched_skills",
        "missing_skills",
        "experience_assessment",
        "project_assessment",
        "suitability_score",
    ]

    missing_keys = [
        key for key in required_keys
        if key not in result
    ]

    if missing_keys:
        raise ValueError(
            f"Claude response is missing keys: {missing_keys}"
        )

    return result
