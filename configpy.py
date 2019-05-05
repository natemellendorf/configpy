from flask import Flask, render_template, redirect, url_for, request, jsonify
import requests
from jinja2 import Environment, FileSystemLoader, meta
from flask_bootstrap import Bootstrap
import yaml, json
from datetime import datetime
from get_ext_repo import get_ext_repo
from flask_socketio import SocketIO
from flask_socketio import emit
import os
import redis
import time
import logging
import fnmatch
from logging.handlers import RotatingFileHandler


app = Flask(__name__)
app.config['secret'] = 's;ldi3r#$R@lkjedf$'
bootstrap = Bootstrap(app)
socketio = SocketIO(app)


if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/microblog.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Microblog startup')


REDIS_URI = os.environ.get('REDIS_URI')

if not REDIS_URI:
    REDIS_URI = '127.0.0.1'

r = redis.Redis(host=REDIS_URI, port=6379, db=0)

dbcheck_stat = 0

def dbcheck_logic(data, **kwargs):
    #print(kwargs)
    current_time = str(datetime.now().time())
    no_sec = current_time.split('.')
    poll = no_sec.pop(0)
    data['last_poll'] = poll

    try:
        found_devices = r.keys()
        #print(found_devices)
        device_dict = {}
        for key in found_devices:
            key = key.decode("utf-8")
            values = r.hgetall(key)
            device_values = {}
            #print(values)
            for x, y in values.items():
                device_values[x.decode("utf-8")] = y.decode("utf-8")
                device_dict[key] = device_values

        #print(device_values)
        if device_dict:
            data['device'] = device_dict
        else:
            data['device'] = ''

    except Exception as e:
        emit('dsc', {'db_error': str(e)}, broadcast=True)
        return

    if 'loopcheck' in kwargs:
        emit('dsc', data, broadcast=True)

    emit('dsc', data)


def dbcheck_loop(data):
    while True:
        dbcheck_logic(data, loopcheck='yes')
        time.sleep(5)


@app.route('/hub', methods=['GET', 'POST'])
def hub():
    return render_template('hub.html', title='Hub')


@app.route('/hub/device/<serialnumber>', methods=['GET'])
def hub_api(serialnumber):
    response = r.hgetall(serialnumber)
    api_request = {}
    for k, v in response.items():
        api_request[k.decode("utf-8")] = v.decode("utf-8")
    response = jsonify(api_request)
    return response


@app.route('/render', methods=['GET', 'POST'])
def render():

    repo_dir = 'repo/'
    debug = ''

    if request.get_json():
        received = request.get_json()
        repo_url = yaml.load(received["repo_url"])

        ext_repo_info = get_ext_repo(repo_url)

        # Convert python dict to JSON, so AJAX can read it.
        result = jsonify(ext_repo_info)
        return result

    foundtemplates = fnmatch.filter(os.listdir(repo_dir), '*.j2')
    return render_template('renderform.html', title='Render Template', foundtemplates=foundtemplates, debug=debug)

@app.route('/process', methods=['POST'])
def process():
    '''
    Note: This whole route needs to be rewritten.
    Today, it takes untrusted and unverified data and saves it to the server.
    Although this isn't a big deal if your source is trusted, I would consider it a very bad practice.
    If it absolutly has to save data to the server (unlikely), it should be run in a container to isolate it.
    However, I'll consider the below good enough for personal project work.
    - Nate Mellendorf
    '''
    received = request.get_json()
    r = requests.get(received["template"])

    if '---' not in received["answers"]:
        return 'Answers must begin with ---'

    with open("repo/render.tmp", "w") as file:
        file.write(r.text)

    env = Environment(loader=FileSystemLoader('repo/'), trim_blocks=True, lstrip_blocks=True)
    ast = env.parse(r.text)
    dependencies = list(meta.find_referenced_templates(ast))
    # print(dependencies)

    if dependencies:
        repo_url = yaml.load(received["repo_url"])
        ext_repo_info = get_ext_repo(repo_url, 'all')
        for key, value in ext_repo_info["files"].items():
            # print(key, value)
            for dependency in dependencies:
                if dependency == key:
                    # print('Process: ' + value)
                    r = requests.get(value)
                    with open("repo/{0}".format(key), "w") as file:
                        file.write(r.text)

    env = Environment(loader=FileSystemLoader('repo/'), trim_blocks=True, lstrip_blocks=True)
    # Load data from YAML into Python dictionary
    answerfile = yaml.load(received["answers"])

    # Load Jinja2 template
    template = env.get_template("render.tmp")

    # Render the template
    try:
        rendered_template = template.render(answerfile)

    except Exception as e:
        return str(e)

    # print(rendered_template)

    return str(rendered_template)


@app.route('/show', methods=['POST'])
def show():
    received = request.get_json()
    #print(received)
    answerfile = str(received[0]['value']).replace('.j2', '.yml')
    r = requests.get(answerfile)

    return r.text


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
# @login_required
def index():
    return redirect(url_for('hub'))


@socketio.on('console')
def test_connect(data):
    current_time = str(datetime.now().time())
    no_sec = current_time.split('.')
    time = no_sec.pop(0)
    data['event_time'] = time
    emit('console', data)


@socketio.on('dsc')
def dsc(data):
    # define global var
    global dbcheck_stat

    # If var is 0, then start the while loop to check DB.
    # It's important to only run this loop once, else, each new user starts a new run.
    if dbcheck_stat == 0:
        # update the global var so the loop is not run again.
        dbcheck_stat = 1
        # Start the loop
        dbcheck_loop(data)

    # If the loops been started but this is a new user request, run the loop logic once.
    # That way, the users web request completes with valid data.
    # Else, the page will load with no data (until the loop runs.)
    dbcheck_logic(data)


@socketio.on('connect')
def connect():
    print('Client connected!')


@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=80)

