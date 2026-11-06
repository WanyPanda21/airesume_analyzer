# AI Resume Analyzer (FastAPI + Streamlit + AWS SAM)

## Flow
Streamlit UI -> POST `/api/resumes/upload-url` -> browser uploads PDF to S3 using the returned presigned URL -> Streamlit sends candidate name, S3 URI, job description and AI toggle to POST `/api/resumes/analyze`.

API Gateway routes are explicit. No `{proxy+}` route is used. SAM's Lambda integration invokes Mangum/FastAPI, where exact application routes are declared.

## Deploy
1. Add GitHub repository secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `CLAUDE_API_KEY`.
2. Set repository variables (optional): `AWS_REGION` (default `ap-southeast-2`), `STACK_NAME` (default `ai-resume-analyzer`).
3. Push to `main`; `.github/workflows/deploy.yml` builds and deploys SAM, creates/updates the Secrets Manager secret from `CLAUDE_API_KEY`, and outputs the API URL.
4. For local UI: install `backend/requirements.txt` and `frontend/requirements.txt`, configure AWS credentials for the local session, then run:
   `streamlit run frontend/app.py`
   Set `API_BASE_URL` to the deployed API base URL.

The AWS resources (S3, DynamoDB, Secrets Manager, API Gateway, Lambda, CloudWatch log group) are declared in `template.yml` and created by SAM/CloudFormation. Do not create them manually.

## Notes
- Candidate name validation rejects digits and unusual punctuation.
- API logs metadata/errors only; it does not log resume text or credentials.
- Skill match percentage is based on the JD's recognized technical skills present in resume text.
