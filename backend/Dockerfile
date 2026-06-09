# Control Plane backend image.
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; wheels cover cryptography/bcrypt on slim.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 9000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
