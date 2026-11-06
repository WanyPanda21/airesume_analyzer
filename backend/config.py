import os

RESUME_BUCKET = os.environ["RESUME_BUCKET"]
CANDIDATES_TABLE = os.environ["CANDIDATES_TABLE"]
ANALYSES_TABLE = os.environ["ANALYSES_TABLE"]
CLAUDE_SECRET_NAME = os.environ["CLAUDE_SECRET_NAME"]
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", "5242880"))
