FROM ubuntu:latest

RUN apt-get update && apt-get install -y python3.11 python3.11-distutils

RUN apt-get install -y python3-pip

RUN pip install redis

COPY ./ ./

RUN pip install -r ./requirements.txt

CMD ["python3","/data/main.py"]