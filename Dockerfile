FROM python:3.12-slim
WORKDIR /app
COPY src/ /app/src/
COPY tests/ /app/tests/
CMD ["python", "-m", "src.server", "--stdio"]
