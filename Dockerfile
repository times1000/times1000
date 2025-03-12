FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including browsers for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Command to run the application
CMD ["python", "main.py"]