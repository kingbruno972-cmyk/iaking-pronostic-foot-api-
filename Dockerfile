FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ne surtout pas fixer de port, Railway le donne automatiquement
EXPOSE 8000

CMD sh -c "uvicorn api.main:app --host 0.0.0.0 --port $PORT"