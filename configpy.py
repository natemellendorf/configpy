from flask import Flask, render_template, redirect, url_for, request, jsonify, g, session
import requests
from jinja2 import Environment, FileSystemLoader, meta
from flask_bootstrap import Bootstrap
import yaml, json
from datetime import datetime
from get_ext_repo import get_ext_repo, pushtorepo
from flask_socketio import SocketIO, emit
import os
import redis
import time
import secrets
import logging
import fnmatch
from logging.handlers import RotatingFileHandler

from flask_github import GitHub
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from pprint import pprint

import requests
import sqlite3
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from flask_apscheduler import APScheduler

# Needed for SocketIO to actually work...
import eventlet
eventlet.monkey_patch()


# Gather secrets
github_secret = secrets.token_urlsafe(40)
flask_secret = secrets.token_urlsafe(40)

github_oauth = False
github_client_id = os.environ.get('GITHUB_CLIENT_ID')
github_client_secret = os.environ.get('GITHUB_CLIENT_SECRET')

if github_client_id and github_client_secret:
    github_oauth = True

app = Flask(__name__)
app.config['secret'] = flask_secret
app.config['GITHUB_CLIENT_ID'] = github_client_id
app.config['GITHUB_CLIENT_SECRET'] = github_client_secret
app.config['SECRET_KEY'] = github_secret
bootstrap = Bootstrap(app)
github = GitHub(app)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
socketio = SocketIO(app, message_queue='redis://redis')


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


# setup sqlalchemy
engine = create_engine('sqlite:////tmp/github-flask.db')
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


def init_db():
    print('creating DB...')
    Base.metadata.create_all(bind=engine)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    github_access_token = Column(String(255))
    github_id = Column(Integer)
    github_login = Column(String(255))

    def __init__(self, github_access_token):
        self.github_access_token = github_access_token


def current_time():
    current_time = str(datetime.now().time())
    no_sec = current_time.split('.')
    time = no_sec.pop(0)
    return time

def static_error(error):
    new_data = {}
    print(error)
    new_data['event_time'] = current_time()
    new_data['event'] = str(error)
    return new_data

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
        socketio.emit('dsc', {'db_error': str(e)}, broadcast=True)
        return

    if 'loopcheck' in kwargs:
        socketio.emit('dsc', data, broadcast=True)

    socketio.emit('dsc', data)


def dbcheck_loop():
    data = {'Get': 'devices'}
    with app.test_request_context('/'):
        while True:
            dbcheck_logic(data, loopcheck='yes')
            # Loop delay
            time.sleep(1)

def GitHubAuthRequired(func):
    def authwrapper(*args, **kwargs):
        if github_oauth is False:
            print('Missing GitHub OAuth ID/Secrets!')
            return redirect(url_for('index'))
        elif g.user:
            return func(*args, **kwargs)
        else:
            print('PLEASE AUTH')
            return github.authorize(scope="user,repo")
    authwrapper.__name__ = func.__name__
    return authwrapper


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.get(session['user_id'])


@app.after_request
def after_request(response):
    db_session.remove()
    return response


@github.access_token_getter
def token_getter():
    user = g.user
    if user is not None:
        return user.github_access_token


@app.route('/github-callback')
@github.authorized_handler
def authorized(access_token):
    
    next_url = request.args.get('next') or url_for('render')
    if access_token is None:
        return redirect(next_url)

    user = User.query.filter_by(github_access_token=access_token).first()
    if user is None:
        user = User(access_token)
        db_session.add(user)

    user.github_access_token = access_token

    # Not necessary to get these details here
    # but it helps humans to identify users easily.
    g.user = user
    github_user = github.get('/user')
    user.github_id = github_user['id']
    user.github_login = github_user['login']

    db_session.commit()

    session['user_id'] = user.id
    return redirect(next_url)


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    return redirect(url_for('hub'))


@app.route('/login')
def login():
    if github_oauth and session.get('user_id', None) is None:
        return github.authorize(scope="user,repo")
    else:
        #print(session['user_id'])
        return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/user')
@GitHubAuthRequired
def user():
    '''
    Auth Example
    '''
    return jsonify(github.get('/user'))


@app.route('/hub', methods=['GET', 'POST'])
def hub():
    return render_template('hub.html', title='Hub')


@app.route('/render', methods=['GET', 'POST'])
@GitHubAuthRequired
def render():

    # Get list of all repos for logged in user
    github_repos = github.get(f'/user/repos')

    '''
    if request.get_json():
        received = request.get_json()
        repo_url = yaml.load(received["repo_url"])

        ext_repo_info = get_ext_repo(repo_url)

        # Convert python dict to JSON, so AJAX can read it.
        result = jsonify(ext_repo_info)
        return result
    '''

    return render_template('renderform.html', title='Render Template', foundrepos=github_repos)


@app.route('/show', methods=['POST'])
def show():
    received = request.get_json()
    answerfile = str(received[0]['value']).replace('.j2', '.yml')
    r = requests.get(answerfile, timeout=5)

    return r.text


@app.route('/hub/device/<serialnumber>', methods=['GET'])
def hub_api(serialnumber):
    response = r.hgetall(serialnumber)
    api_request = {}
    for k, v in response.items():
        api_request[k.decode("utf-8")] = v.decode("utf-8")
    response = jsonify(api_request)
    return response


@app.route('/process', methods=['POST'])
def process():

    '''
    Note: This whole route needs to be rewritten.
    Today, it takes untrusted and unverified data and saves it to the server.
    Although this isn't a big deal if your source is trusted, I would consider it a very bad practice.
    If it absolutely has to save data to the server (doubt), it should be run in a container to isolate it.
    '''

    received = request.get_json()

    pprint(received)

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
                    r = requests.get(value, timeout=5)
                    with open("repo/{0}".format(key), "w") as file:
                        file.write(r.text)

    env = Environment(loader=FileSystemLoader('repo/'), trim_blocks=True, lstrip_blocks=True)

    try:
        # Load data from YAML into Python dictionary
        answerfile = yaml.load(received["answers"])
        # Load Jinja2 template
        template = env.get_template("render.tmp")
        # Render the template
        rendered_template = template.render(answerfile)

    except Exception as e:
        # If errors, return them to UI.
        return str(e)

    return str(rendered_template)


@socketio.on('console')
def test_connect(data):
    current_time = str(datetime.now().time())
    no_sec = current_time.split('.')
    time = no_sec.pop(0)
    data['event_time'] = time
    socketio.emit('console', data)


@socketio.on('hub_console')
def hub_console(data):
    socketio.emit('hub_console', data)


@socketio.on('getRepo')
def getRepo(form):
    form = json.loads(form['data'])
    
    #github.authorize()
    g.user = None
    if 'user_id' in session:
        g.user = User.query.get(session['user_id'])

    if form.get('selected_repo', None) and form.get('github_user', None):
        repo = form['selected_repo']
        user = form['github_user']
        contents = f'/repos/{user}/{repo}/contents/'

        gh_repo_contents = github.get(contents)

        ext_repo_files = {}
        ext_repo_info = {}

        for path in gh_repo_contents:
            if '.j2' in path['path']:
                filename = path['path'].replace("j2", "yml")
                for yaml_search in gh_repo_contents:
                    if filename in yaml_search['path']:
                        ext_repo_files[path['path']] = path['download_url']

        ext_repo_info['files'] = ext_repo_files

        emit('repoContent', ext_repo_info)


@socketio.on('getDevice')
def getDevice(data):
    #print(data)
    if data['device']:
        values = r.hgetall(data['device'])
        device_values = {}
        #print(values)
        for x, y in values.items():
            device_values[x.decode("utf-8")] = y.decode("utf-8")

        socketio.emit('foundDevice', device_values)

@socketio.on('deleteDevice')
def deleteDevice(data):
    #print(data)
    if data['deleteDevice']:
        r.delete(data['deleteDevice'])
        #socketio.emit('dsc', 'Delete device refresh')
        socketio.emit('deletedDevice', f'Removed: {data["deleteDevice"]}')


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
        app.apscheduler.add_job(func=dbcheck_loop, trigger='date', id='loop')

    # If the loops been started but this is a new user request, run the loop logic once.
    # That way, the users web request completes with valid data.
    # Else, the page will load with no data (until the loop runs.)
    dbcheck_logic(data)

@socketio.on('gitlabPush')
def gitlabPush(data):
    data = json.loads(data)

    if data['clientID'] \
            and data['repo_auth_token'] \
            and data['serialNumber'] \
            and data['device_config'] \
            and data['repo_uri']:

        for node, serialNumber in data['serialNumber'].items():
            if serialNumber:
                print(f'Pushing node: {node} - serial: {serialNumber}')
                new_data = pushtorepo(data=data, REDIS_URI=REDIS_URI, serialNumber=serialNumber, node=node)
                socketio.emit('git_console', new_data)
            else:
                new_data = dict()
                new_data['event_time'] = current_time()
                new_data['event'] = f'Ignored: {node}'
                socketio.emit('git_console', new_data)

    else:
        new_data = dict()
        new_data['event_time'] = current_time()
        new_data['event'] = 'The form submitted is missing values.'
        socketio.emit('git_console', new_data)


@socketio.on('connect')
def connect():
    print('Client connected!')


@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')


if __name__ == '__main__':
    init_db()
    socketio.run(app, host="0.0.0.0", port=80, debug=True)

