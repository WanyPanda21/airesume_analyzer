import json
import logging
import boto3
from anthropic import Anthropic
from backend.config import CLAUDE_SECRET_NAME, CLAUDE_MODEL

logger = logging.getLogger(__name__)
secrets = boto3.client("secretsmanager")

def get_api_key() -> str:
    result = secrets.get_secret_value(SecretId=CLAUDE_SECRET_NAME)
    secret = result.get("SecretString", "")
    try:
        parsed = json.loads(secret)
        return parsed.get("CLAUDE_API_KEY") or parsed.get("api_key") or secret
    except json.JSONDecodeError:
        return secret

def analyze_with_claude(resume_text: str, job_description: str, skill_result: dict) -> dict:
    client = Anthropic(api_key=get_api_key())
    prompt = f"""Analyze the resume against the job description. Return valid JSON with keys:
overall_assessment, strengths (array), gaps (array), recommendations (array), suitability_score (integer 0-100).
Use factual evidence and do not invent experience.

Resume text:
{resume_text[:18000]}

Job description:
{job_description[:12000]}

Python skill comparison:
{json.dumps(skill_result)}
"""
    logger.info("Calling Claude API model=%s", CLAUDE_MODEL)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Claude response was not JSON; returning text summary")
        return {"overall_assessment": raw, "raw_response": raw}
