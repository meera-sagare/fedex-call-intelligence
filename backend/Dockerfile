FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Set INSTALL_TRANSCRIPTION=false to skip the (large) Whisper speech-to-text dependency.
ARG INSTALL_TRANSCRIPTION=true
COPY requirements.txt requirements-transcription.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_TRANSCRIPTION" = "true" ]; then pip install --no-cache-dir -r requirements-transcription.txt; fi

COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
