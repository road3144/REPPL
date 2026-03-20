import os

# .env 파일이 있으면 로드 (nohup 백그라운드 실행 시 환경변수 유지용)
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_ENV_FILE):
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_CONSUMER_GROUP_ID = os.environ.get("KAFKA_CONSUMER_GROUP_ID", "reppl-gpu")
KAFKA_TOPIC_JOB_REQUEST = os.environ.get("KAFKA_TOPIC_JOB_REQUEST", "reppl.job.request.v1")
KAFKA_TOPIC_JOB_PROGRESS = os.environ.get("KAFKA_TOPIC_JOB_PROGRESS", "reppl.job.progress.v1")

# GMS API
GMS_API_KEY = os.environ.get("GMS_API_KEY", "")

# AWS S3
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY", "")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "")
