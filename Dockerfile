FROM python:3.6-alpine
MAINTAINER Johannes Scheuermann <joh.scheuer@gmail.com>

RUN pip install --no-cache-dir --upgrade kubernetes pyyaml
COPY quobyte /deployer/quobyte
COPY quobyte-k8s-deployer.py /deployer/
COPY config.yaml.example /deployer/config.yaml
RUN chmod +x /deployer/quobyte-k8s-deployer.py

WORKDIR /deployer

CMD python3 -u /deployer/quobyte-k8s-deployer.py