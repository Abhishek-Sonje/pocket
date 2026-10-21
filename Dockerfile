FROM python:3.14-slim
WORKDIR /pocket
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
ENV POCKET_DATA_DIR=/data
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
