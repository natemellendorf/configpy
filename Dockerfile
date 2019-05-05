FROM ubuntu:18.04

RUN apt-get update && apt-get -y upgrade

RUN apt-get -y install python3 python3-venv python3-dev python3-pip git

RUN mkdir /home/devops

WORKDIR /home/devops

RUN git clone https://github.com/natemellendorf/configpy.git

WORKDIR /home/devops/configpy

RUN chmod +x /home/devops/configpy/boot.sh

RUN python3 -m pip install --upgrade pip

RUN pip3 install -r requirements.txt

RUN pip3 install gunicorn

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

EXPOSE 5000

ENTRYPOINT ["/bin/bash", "/home/devops/configpy/boot.sh"]