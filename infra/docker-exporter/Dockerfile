FROM python:3.11-alpine
WORKDIR /app
COPY docker_exporter.py .
EXPOSE 9417
CMD ["python", "-u", "docker_exporter.py"]
