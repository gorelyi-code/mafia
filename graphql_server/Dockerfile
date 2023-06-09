FROM python:3.10-slim

WORKDIR server

COPY graphql_server/mafia.graphql .
COPY graphql_server/main.py .
COPY graphql_server/requirements.txt .

RUN pip install -r requirements.txt

CMD ["python3", "main.py"]
