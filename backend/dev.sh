#!/bin/bash
source .env
# Set default values for environment variables
PORT="${PORT:-8080}"
STORAGE_PROVIDER="${STORAGE_PROVIDER:-}"
S3_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID:-}"
S3_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY:-}"
S3_BUCKET_NAME="${S3_BUCKET_NAME:-}"
S3_REGION_NAME="${S3_REGION_NAME:-us-west-2}"
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-https://s3.us-west-2.amazonaws.com}"

GOKNOWB_API_URL="${GOKNOWB_API_URL:-}"
GOKNOWB_API_KEY="${GOKNOWB_API_KEY:-}"

# Debug: Print environment variables
echo "Debug: Environment Variables"
echo "STORAGE_PROVIDER: ${STORAGE_PROVIDER}"
echo "S3_ACCESS_KEY_ID: ${S3_ACCESS_KEY_ID}"
echo "S3_BUCKET_NAME: ${S3_BUCKET_NAME}"
echo "S3_REGION_NAME: ${S3_REGION_NAME}"
echo "S3_ENDPOINT_URL: ${S3_ENDPOINT_URL}"
echo "PORT: ${PORT}"
echo "GOKNOWB_API_URL: ${GOKNOWB_API_URL}"
echo "GOKNOWB_API_KEY: ${GOKNOWB_API_KEY}"

# Run uvicorn with environment variables
env \
    STORAGE_PROVIDER="${STORAGE_PROVIDER}" \
    S3_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID}" \
    S3_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY}" \
    S3_BUCKET_NAME="${S3_BUCKET_NAME}" \
    S3_REGION_NAME="${S3_REGION_NAME}" \
    S3_ENDPOINT_URL="${S3_ENDPOINT_URL}" \
    uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload