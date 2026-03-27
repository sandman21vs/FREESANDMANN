FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

RUN python init_db.py

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "--timeout", "120", "app:app"]
