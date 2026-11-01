FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY sql ./sql
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "robodata.api:app", "--host", "0.0.0.0", "--port", "8000"]
