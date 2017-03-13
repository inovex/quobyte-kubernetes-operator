FROM centos:7
MAINTAINER Johannes Scheuermann <johannes.scheuermann@inovex.de>

ADD run.sh /usr/bin/local/run.sh

RUN chmod +x /usr/bin/local/run.sh && \
    yum -y -e 0 -d 0 install parted xfsprogs file && \
    yum clean all

CMD ["/bin/bash", "-xec", "/bin/nsenter -t 1 -r -w -m -- ./usr/bin/local/run.sh"]
