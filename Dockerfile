FROM python:3
MAINTAINER Johannes Scheuermann <joh.scheuer@gmail.com>

RUN pip install --no-cache-dir --upgrade kubernetes pyyaml
ADD quobyte /deployer/quobyte
ADD quobyte-k8s-deployer.py /deployer/
RUN chmod +x /deployer/quobyte-k8s-deployer.py