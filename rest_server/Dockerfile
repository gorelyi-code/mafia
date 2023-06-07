FROM python:3.10-slim

WORKDIR server

COPY lib lib
COPY rest_server/main.py .
COPY rest_server/requirements.txt .

RUN pip install -r requirements.txt

CMD ["python3", "main.py"]
