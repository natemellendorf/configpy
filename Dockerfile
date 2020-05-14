FROM ubuntu:18.04
ENV DEBIAN_FRONTEND=noninteractive 
RUN mkdir /home/devops
WORKDIR /home/devops
RUN apt-get update && apt-get -y upgrade
RUN apt-get -y install python3 python3-venv python3-dev python3-pip git tzdata
RUN git clone https://github.com/natemellendorf/configpy.git
WORKDIR /home/devops/configpy
RUN git checkout tags/v0.2.1 -b feature/github
RUN python3 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
EXPOSE 80
ENTRYPOINT python3 configpy.py
