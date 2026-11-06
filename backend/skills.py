import re

# Lightweight starter taxonomy; extend this list as needed.
TECH_SKILLS = {
    "python", "java", "javascript", "typescript", "c#", "c++", "go", "ruby",
    "django", "fastapi", "flask", "spring", "node.js", "react", "angular",
    "rest api", "api gateway", "aws lambda", "lambda", "aws", "s3", "dynamodb",
    "sql", "mysql", "postgresql", "mongodb", "redis", "docker", "kubernetes",
    "git", "github actions", "ci/cd", "terraform", "linux", "pandas",
    "machine learning", "generative ai", "langchain", "rag", "html", "css",
}

def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9+#./ -]", " ", text.lower())

def extract_skills(text: str) -> list[str]:
    haystack = f" {normalized(text)} "
    found = []
    for skill in sorted(TECH_SKILLS, key=len, reverse=True):
        needle = f" {normalized(skill)} "
        if needle in haystack and skill not in found:
            found.append(skill)
    return sorted(found)

def compare_skills(resume_text: str, job_description: str) -> dict:
    jd_skills = extract_skills(job_description)
    resume_skills = set(extract_skills(resume_text))
    matched = [skill for skill in jd_skills if skill in resume_skills]
    missing = [skill for skill in jd_skills if skill not in resume_skills]
    percentage = round((len(matched) / len(jd_skills)) * 100) if jd_skills else 0
    return {
        "job_description_skills": jd_skills,
        "resume_skills": sorted(resume_skills),
        "matched_skills": matched,
        "missing_skills": missing,
        "technical_skill_match_percentage": percentage,
    }
