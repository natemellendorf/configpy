#!/bin/sh
cd /home/devops/configpy
gunicorn --worker-class eventlet -b 0.0.0.0:5000 -w 4 wsgi:socketio