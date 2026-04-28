FROM python:3.12-alpine

WORKDIR /app
COPY . /app
EXPOSE 47865
CMD ["python3", "scripts/crm_module.py", "serve", "--host", "0.0.0.0", "--port", "47865"]
