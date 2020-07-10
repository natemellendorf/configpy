FROM ubuntu:18.04
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive 

RUN apt-get update && apt-get -y upgrade
RUN apt-get -y install python3 python3-venv python3-dev python3-pip git tzdata openssl
RUN python3 -m pip install --upgrade pip

RUN useradd -rm -d /home/unprivileged -s /bin/bash -g root -G sudo -p "$(openssl passwd -1 unprivileged)" -u 1001 unprivileged
USER unprivileged
WORKDIR /home/unprivileged

RUN git clone https://github.com/natemellendorf/configpy.git
WORKDIR /home/unprivileged/configpy
RUN git checkout configpy/standalone

ENV PATH "$PATH:/home/unprivileged/.local/bin"

RUN pip3 install --user -r requirements.txt

EXPOSE 80
ENTRYPOINT python3 configpy.py
