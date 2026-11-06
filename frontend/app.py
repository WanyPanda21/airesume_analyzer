import os
import requests
import streamlit as st
import boto3

st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄", layout="centered")
st.title("AI Resume Analyzer")
st.caption("Compare your resume with a job description. AI feedback is optional.")

api_base = os.getenv("API_BASE_URL", "https://y49i1qkwd5.execute-api.ap-southeast-2.amazonaws.com/prod").rstrip("/")
if not api_base:
    st.error("Set API_BASE_URL to your deployed API Gateway base URL.")
    st.stop()

with st.form("resume_analysis_form"):
    candidate_name = st.text_input("Candidate name", placeholder="Enter your valid name")
    resume_file = st.file_uploader("Upload resume (PDF only)", type=["pdf"])
    job_description = st.text_area("Job description", height=220, placeholder="Paste the job description here...")
    analyze_with_ai = st.toggle("Analyze with Claude AI", value=False)
    submitted = st.form_submit_button("Analyze resume", type="primary")

if submitted:
    if not candidate_name.strip() or not resume_file or len(job_description.strip()) < 30:
        st.error("Please provide a valid name, PDF resume, and job description (at least 30 characters).")
        st.stop()
    try:
        with st.spinner("Preparing secure S3 upload..."):
            url_response = requests.post(
                f"{api_base}/api/resumes/upload-url",
                json={"candidate_name": candidate_name, "filename": resume_file.name},
                timeout=30,
            )
            url_response.raise_for_status()
            upload_info = url_response.json()

        with st.spinner("Uploading PDF to S3..."):
            upload_response = requests.put(
                upload_info["upload_url"],
                data=resume_file.getvalue(),
                headers={"Content-Type": "application/pdf"},
                timeout=60,
            )
            upload_response.raise_for_status()

        with st.spinner("Analyzing resume..."):
            response = requests.post(
                f"{api_base}/api/resumes/analyze",
                json={
                    "candidate_name": candidate_name,
                    "s3_resume_path": upload_info["s3_resume_path"],
                    "job_description": job_description,
                    "analyze_with_ai": analyze_with_ai,
                },
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()

        st.success("Analysis completed!")
        st.metric("Technical skill match", f'{result["technical_skill_match_percentage"]}%')
        st.write("**Matched skills**", result["matched_skills"])
        st.write("**Missing skills**", result["missing_skills"])
        if result.get("ai_feedback"):
            st.subheader("Claude AI feedback")
            st.json(result["ai_feedback"])
        with st.expander("Analysis record"):
            st.json(result)
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.text
        except Exception:
            pass
        st.error(f"Request failed: {detail or exc}")
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
