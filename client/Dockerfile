FROM python:3.10-slim

WORKDIR client

COPY proto/mafia.proto proto/mafia.proto
COPY lib lib
COPY client/main.py .
COPY client/requirements.txt .

RUN pip install -r requirements.txt

RUN python3 -m grpc_tools.protoc -Iproto --python_out=proto --grpc_python_out=proto proto/mafia.proto
RUN sed -i -e 's/import mafia_pb2 as mafia__pb2/import proto.mafia_pb2 as mafia__pb2/g' proto/mafia_pb2_grpc.py

CMD ["python3", "main.py"]
