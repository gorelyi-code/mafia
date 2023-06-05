FROM python:3.10-slim

WORKDIR server

COPY proto/mafia.proto proto/mafia.proto
COPY server/main.py .
COPY server/requirements.txt .

RUN pip install -r requirements.txt

RUN python3 -m grpc_tools.protoc -Iproto --python_out=. --grpc_python_out=. proto/mafia.proto

CMD ["python3", "main.py"]
