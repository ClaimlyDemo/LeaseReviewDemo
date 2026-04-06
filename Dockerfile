FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY run_cli.py ./

RUN pip install --upgrade pip && pip install .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "lease_review_tool.api:app", "--host", "0.0.0.0", "--port", "8000"]