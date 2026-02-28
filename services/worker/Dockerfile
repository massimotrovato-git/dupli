FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir sqlalchemy psycopg[binary] redis rq requests
COPY . /app
CMD ["python", "-m", "worker.run"]
