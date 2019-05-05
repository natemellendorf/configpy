#!/bin/sh
cd /home/devops/configpy
flask run --host 0.0.0.0 --port 80
#gunicorn --worker-class eventlet -b 0.0.0.0:5000 -w 4 wsgi:app