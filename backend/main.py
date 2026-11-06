import io
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

import boto3
from fastapi import FastAPI, HTTPException
from mangum import Mangum
from pydantic import BaseModel, Field
from pypdf import PdfReader

from backend.config import RESUME_BUCKET, CANDIDATES_TABLE, ANALYSES_TABLE, MAX_PDF_BYTES
from backend.skills import compare_skills
from backend.claude_service import analyze_with_claude

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("resume-analyzer")

app = FastAPI(title="AI Resume Analyzer", version="1.0.0")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
candidate_table = dynamodb.Table(CANDIDATES_TABLE)
analysis_table = dynamodb.Table(ANALYSES_TABLE)

class UploadUrlRequest(BaseModel):
    candidate_name: str = Field(min_length=2, max_length=80)
    filename: str = Field(min_length=1, max_length=200)

class AnalyzeRequest(BaseModel):
    candidate_name: str = Field(min_length=2, max_length=80)
    s3_resume_path: str
    job_description: str = Field(min_length=30, max_length=20000)
    analyze_with_ai: bool = False

def validate_name(name: str) -> str:
    cleaned = " ".join(name.strip().split())
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,79}", cleaned):
        raise HTTPException(status_code=422, detail="Enter a valid name (letters, spaces, apostrophe, dot or hyphen only).")
    return cleaned

def parse_s3_uri(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"s3://([^/]+)/(.+)", uri.strip())
    if not match:
        raise HTTPException(status_code=400, detail="s3_resume_path must be a valid s3://bucket/key URI.")
    bucket, key = match.groups()
    if bucket != RESUME_BUCKET or not key.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF stored in the configured resume bucket.")
    return bucket, key

@app.post("/api/resumes/upload-url")
def create_upload_url(payload: UploadUrlRequest):
    candidate_name = validate_name(payload.candidate_name)
    filename = payload.filename.rsplit("/", 1)[-1]
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF resumes are accepted.")
    candidate_id = str(uuid4())
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    key = f"resumes/{candidate_id}/{safe_filename}"
    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": RESUME_BUCKET, "Key": key, "ContentType": "application/pdf"},
            ExpiresIn=300,
        )
        logger.info("Generated upload URL candidate_id=%s", candidate_id)
        return {"candidate_id": candidate_id, "upload_url": url, "s3_resume_path": f"s3://{RESUME_BUCKET}/{key}"}
    except Exception:
        logger.exception("Failed to generate S3 upload URL")
        raise HTTPException(status_code=500, detail="Could not create resume upload URL.")

@app.post("/api/resumes/analyze")
def analyze_resume(payload: AnalyzeRequest):
    candidate_name = validate_name(payload.candidate_name)
    bucket, key = parse_s3_uri(payload.s3_resume_path)
    analysis_id = str(uuid4())
    candidate_id = key.split("/")[1] if key.startswith("resumes/") else str(uuid4())
    logger.info("Analysis started analysis_id=%s candidate_id=%s ai_enabled=%s", analysis_id, candidate_id, payload.analyze_with_ai)
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        pdf_bytes = obj["Body"].read(MAX_PDF_BYTES + 1)
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF exceeds the 5 MB limit.")
        reader = PdfReader(io.BytesIO(pdf_bytes))
        resume_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not resume_text:
            raise HTTPException(status_code=422, detail="No readable text found in PDF. Please upload a text-based PDF.")
        skill_result = compare_skills(resume_text, payload.job_description)
        ai_feedback = analyze_with_claude(resume_text, payload.job_description, skill_result) if payload.analyze_with_ai else None
        timestamp = datetime.now(timezone.utc).isoformat()
        candidate_table.put_item(Item={
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "s3_resume_path": payload.s3_resume_path,
            "created_at": timestamp,
        })
        result = {
            "analysis_id": analysis_id,
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "s3_resume_path": payload.s3_resume_path,
            "job_description": payload.job_description,
            "analyze_with_ai": payload.analyze_with_ai,
            **skill_result,
            "ai_feedback": ai_feedback,
            "created_at": timestamp,
        }
        analysis_table.put_item(Item=result)
        logger.info("Analysis completed analysis_id=%s match=%s", analysis_id, skill_result["technical_skill_match_percentage"])
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Analysis failed analysis_id=%s", analysis_id)
        raise HTTPException(status_code=500, detail="Resume analysis failed. Check CloudWatch logs.")

@app.get("/api/resumes/history")
def get_history():
    try:
        response = analysis_table.scan(Limit=50)
        items = response.get("Items", [])
        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return {"items": items}
    except Exception:
        logger.exception("Failed to fetch analysis history")
        raise HTTPException(status_code=500, detail="Could not fetch analysis history.")

@app.get("/api/resumes/{analysis_id}")
def get_analysis(analysis_id: str):
    try:
        response = analysis_table.get_item(Key={"analysis_id": analysis_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Analysis not found.")
        return item
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to retrieve analysis_id=%s", analysis_id)
        raise HTTPException(status_code=500, detail="Could not retrieve analysis.")

handler = Mangum(app)
