FROM python:3.10-slim

WORKDIR client

COPY proto/mafia.proto proto/mafia.proto
COPY client/main.py .
COPY client/requirements.txt .

RUN pip install -r requirements.txt

RUN python3 -m grpc_tools.protoc -Iproto --python_out=. --grpc_python_out=. proto/mafia.proto

CMD ["python3", "main.py"]
