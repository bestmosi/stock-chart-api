# استفاده از Python 3.11 slim image
FROM python:3.11-slim

# تنظیم working directory
WORKDIR /app

# نصب system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# کپی requirements
COPY requirements.txt .

# نصب Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# کپی application code
COPY stock_chart_api.py .

# ایجاد directory برای charts
RUN mkdir -p generated_charts

# تنظیم environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# اجرای application با gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 stock_chart_api:app
