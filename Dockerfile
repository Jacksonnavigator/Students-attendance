FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Make port 7860 available
EXPOSE 7860

# Define environment variable for Flask
ENV FLASK_APP=app.py

# Run gunicorn server when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app:app"]
