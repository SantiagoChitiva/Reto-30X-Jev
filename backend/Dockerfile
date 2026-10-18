# Se construye desde la raíz del repo (docker-compose.yml y la nube usan el mismo archivo),
# para que la imagen lleve también los perfiles de data/.
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt
COPY backend/app ./app
COPY backend/db ./db
COPY data/perfiles_30x.json data/labeled_set.json data/eval_results.json /data/
ENV DATA_DIR=/data
EXPOSE 8000
# La nube define PORT; en local es 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
