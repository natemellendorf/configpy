#!/bin/sh
cd /home/devops/configpy
python configpy.py
#flask run --host 0.0.0.0 --port 80
#gunicorn --worker-class eventlet -b 0.0.0.0:5000 -w 1 wsgi:app