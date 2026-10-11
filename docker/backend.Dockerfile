FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY kb kb
COPY data/samples data/samples
# Download Chroma's embedding model at build time, so the container works offline.
RUN RCF_CHROMA_DIR=/tmp/chroma-warmup python -c "import sys; sys.path.insert(0, 'backend'); \
from rcf.kb import KnowledgeBase; KnowledgeBase().search('warm up')" && rm -rf /tmp/chroma-warmup
ENV RCF_DB=/app/state/rcf.db RCF_CHROMA_DIR=/app/state/chroma
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=12 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
