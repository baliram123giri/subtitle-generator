# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make port 3300 available to the world outside this container
EXPOSE 3300

# Run the application on port 3300
CMD ["gunicorn", "--bind", "0.0.0.0:3300", "main:app"]
