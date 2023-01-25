FROM python:3.11
ENV PYTHONBUFFERED 1
WORKDIR /django_project
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY .. django_project
CMD python manage.py runserver 0.0.0.0:8000
