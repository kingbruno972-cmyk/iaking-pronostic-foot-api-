# ---- Base Python image ----
FROM python:3.10-slim

# ---- Set working directory ----
WORKDIR /app

# ---- Copy project files ----
COPY . /app

# ---- Install dependencies ----
RUN pip install --no-cache-dir -r requirements.txt

# ---- Expose the port ----
EXPOSE 8000

# ---- Start API with Uvicorn ----
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]