import os
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables
load_dotenv()

# Google Sheets Configuration
SERVICE_ACCOUNT_INFO: Dict[str, Any] = {
    "type": "service_account",
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv("GOOGLE_CERT_URL"),
    "universe_domain": "googleapis.com"
}

# Spreadsheet Configuration
SPREADSHEET_CONFIG = {
    "SHEET_ID": os.getenv("SPREADSHEET_ID"),
    "EMAILS_SHEET": "emails",
    "ORDERS_SHEET": "orders",
    "PRODUCTS_SHEET": "products"
}

# LLM Configuration
LLM_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    "model_name": os.getenv("LLM_MODEL", "gpt-4"),
    "temperature": float(os.getenv("LLM_TEMPERATURE", 0.3)),
    "max_retries": int(os.getenv("LLM_MAX_RETRIES", 3))
}

# Email Processing
EMAIL_CONFIG = {
    "MAX_EMAILS_PER_BATCH": 50,
    "DEFAULT_SENDER": os.getenv("DEFAULT_EMAIL_SENDER"),
    "ARCHIVE_FOLDER": "processed_emails"
}

# Logging Configuration
LOGGING_CONFIG = {
    "LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    "FILE": "logs/app.log",
    "MAX_SIZE": 1024 * 1024 * 5,  # 5MB
    "BACKUP_COUNT": 3
}