FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app/backend

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
