FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY python ./python
COPY data ./data

EXPOSE 5005 8080

CMD ["python", "python/most_runs_by_year.py", "--server"]