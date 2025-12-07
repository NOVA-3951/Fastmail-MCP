FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fastmail_mcp.py .
COPY main.py .

EXPOSE 8081

CMD ["python", "main.py"]
