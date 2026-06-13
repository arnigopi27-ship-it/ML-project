# Use an official Python runtime as a parent image
FROM python:3.11.9-slim

# Install Tesseract OCR and other system dependencies required by cv2 and pytesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY backend/requirements.txt ./backend/

# Install the required Python packages
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the frontend and backend directories
COPY frontend/ ./frontend/
COPY backend/ ./backend/

# Expose port 5000
EXPOSE 5000

# Change working directory to backend so Flask finds the DB and frontend files properly
WORKDIR /app/backend

# Run the app using Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
