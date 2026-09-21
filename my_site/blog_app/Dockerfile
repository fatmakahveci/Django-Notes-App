FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY my_site/blog_app/requirements.txt ./my_site/blog_app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY my_site/ ./my_site/
WORKDIR /app/my_site
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
