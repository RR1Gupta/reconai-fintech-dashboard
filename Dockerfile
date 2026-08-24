FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Regenerate data at build time so the container is self-contained
RUN python generate_data.py --n 60 --seed 42

EXPOSE 5000

CMD ["python", "app.py"]
