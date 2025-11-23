# ---- 1. Image de base ----
FROM python:3.10-slim

# ---- 2. Dossier de l'app ----
WORKDIR /app

# ---- 3. Copier requirements ----
COPY requirements.txt .

# ---- 4. Installer dépendances ----
RUN pip install --no-cache-dir -r requirements.txt

# ---- 5. Copier ton code ----
COPY . .

# ---- 6. Exposer le port ----
EXPOSE 8000

# ---- 7. Commande de démarrage ----
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]