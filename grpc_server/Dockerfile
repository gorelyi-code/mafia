FROM python:3.10-slim

WORKDIR server

COPY proto/mafia.proto proto/mafia.proto
COPY grpc_server/lib lib
COPY grpc_server/main.py .
COPY grpc_server/requirements.txt .

RUN pip install -r requirements.txt

RUN python3 -m grpc_tools.protoc -Iproto --python_out=proto --grpc_python_out=proto proto/mafia.proto
RUN sed -i -e 's/import mafia_pb2 as mafia__pb2/import proto.mafia_pb2 as mafia__pb2/g' proto/mafia_pb2_grpc.py

CMD ["python3", "main.py"]
