import os
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()

Config = {
    "NEO4J_URI": os.getenv('NEO4J_URI', None),
    "NEO4J_USER": os.getenv('NEO4J_USER', None),
    "NEO4J_PASSWORD": os.getenv('NEO4J_PASSWORD', None),
    "POSTGRES_URL": os.getenv('POSTGRES_URL', 'postgresql://admin:pechaAdmin@localhost:5435/pecha'),
    
    # AWS SQS Configuration
    "AWS_REGION": os.getenv('AWS_REGION', 'us-east-1'),
    "AWS_ACCESS_KEY_ID": os.getenv('AWS_ACCESS_KEY_ID', None),
    "AWS_SECRET_ACCESS_KEY": os.getenv('AWS_SECRET_ACCESS_KEY', None),
    "SQS_QUEUE_URL": os.getenv('SQS_QUEUE_URL', None),

    "WEBUDDHIST_API_ENDPOINT": os.getenv('WEBUDDHIST_API_ENDPOINT', None),
    "WEBUDDHIST_LOG_IN_EMAIL": os.getenv('WEBUDDHIST_LOG_IN_EMAIL', None),
    "WEBUDDHIST_LOG_IN_PASSWORD": os.getenv('WEBUDDHIST_LOG_IN_PASSWORD', None),
}


def get(key: str, default=None):
    return Config.get(key, default)