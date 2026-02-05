FROM python:3.11-slim

RUN apt-get update

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["hypercorn", "-w", "4", "--bind", "0.0.0.0:3000", "--config", "hypercorn.toml", "main:app"]


