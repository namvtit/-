# The factory's packaging of the pinned, unmodified upstream sources.
# Bookworm avoids upstream Bullseye security packages that return 404.
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /MoneyPrinterTurbo
ENV PYTHONPATH=/MoneyPrinterTurbo
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
