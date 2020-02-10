from flask import Flask, render_template, redirect, url_for, request, jsonify, g, session
import requests
from jinja2 import Environment, FileSystemLoader, meta
from flask_bootstrap import Bootstrap
import yaml
import json
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
github_client_id = os.environ.get('GITHUB_CLIENT_ID', None)
github_client_secret = os.environ.get('GITHUB_CLIENT_SECRET', None)
GITHUB_ORG = os.environ.get('GITHUB_ORG', None)

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
app.logger.info('ConfigPy startup')

REDIS_URI = os.environ.get('REDIS_URI', '127.0.0.1')

r = redis.Redis(host=REDIS_URI, port=6379, db=0)
r_app = redis.Redis(host=REDIS_URI, port=6379, db=1, decode_responses=True, charset="utf-8")

dbcheck_stat = 0

class dotdict(dict):
    def __getattr__(self, name):
        return self[name]

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
        device_dict = {}
        for key in found_devices:
            key = key.decode("utf-8")
            values = r.hgetall(key)
            device_values = {}
            for x, y in values.items():
                device_values[x.decode("utf-8")] = y.decode("utf-8")
                device_dict[key] = device_values

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
            print('Authentication needed')
            return github.authorize(scope="user,repo")
    authwrapper.__name__ = func.__name__
    return authwrapper

@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        get = r_app.hgetall(session['user_id'])
        g.user = dotdict(get)

@app.after_request
def after_request(response):
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

    user = None
    found_users = r_app.keys()

    if found_users:
        print('Users were found in DB!')
        for user in found_users:
            current_user = r_app.hgetall(user)
            if current_user['github_access_token']:
                user = r_app.hgetall(user)
    else:
        print('No users in current DB..')

    github_user = github.raw_request('GET','/user', access_token=access_token)
    github_user = json.loads(github_user.text)
    github_login = github_user['login']

    if user is None:
        r_app.hmset(github_login, {'github_access_token':access_token})
        r_app.expire(github_login, 60)
        user = r_app.hgetall(github_login)

    r_app.hmset(github_login, {'github_id': github_user["id"]})
    r_app.hmset(github_login, {'github_login': github_user["login"]})

    user = r_app.hgetall(github_login)
    user = dotdict(user)
    g.user = user
    session['user_id'] = user.github_login

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
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    if session:
        status = session.pop('user_id', None)

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

    if GITHUB_ORG:
        result = github.get(f'/search/repositories?q=org:{GITHUB_ORG}+configpy+in:readme')
        github_repos = result.get('items', [''])
    else:
        result = github.get(f'/search/repositories?q=user:{g.user.github_login}+configpy+in:readme')
        github_repos = result.get('items', [''])

    return render_template('renderform.html', title='Render Template', foundrepos=github_repos)

@app.route('/show', methods=['POST'])
def show():
    received = request.get_json()
    answerfile = str(received[0]['value']).replace('.j2', '.yml')
    r = github.raw_request(method='GET', resource=answerfile)

    return r.text

@app.route('/hub/device/<serialnumber>', methods=['GET'])
def hub_api(serialnumber):
    response = r.hgetall(serialnumber)
    api_request = {}
    for k, v in response.items():
        api_request[k.decode("utf-8")] = v.decode("utf-8")
    response = jsonify(api_request)
    return response

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

@socketio.on('render_template')
def process(form):
    
    g.user = None
    if 'user_id' in session:
        get_user = r_app.hgetall(session['user_id'])
        g.user = dotdict(get_user)
    
    form = json.loads(form['data'])
    repo = form.get('selected_repo')
    answers = form.get('answers')
    user = g.user.github_login

    r = requests.get(form["template"])

    if '---' not in form["answers"]:
        return 'Answers must begin with ---'

    with open("repo/render.tmp", "w") as file:
        file.write(r.text)

    env = Environment(loader=FileSystemLoader('repo/'), trim_blocks=True, lstrip_blocks=True)
    ast = env.parse(r.text)
    dependencies = list(meta.find_referenced_templates(ast))

    if dependencies:

        if GITHUB_ORG:
            org_contents = f'/repos/{GITHUB_ORG}/{repo}/contents/'
            repo_contents = github.get(org_contents)

        else:
            personal_contents = f'/repos/{user}/{repo}/contents/'
            repo_contents = github.get(personal_contents)
        
        ext_repo_files = {}

        for item in repo_contents:
            if '.j2' in item['path']:
                ext_repo_files[item['path']] = item['download_url']

        for key, value in ext_repo_files.items():
            for dependency in dependencies:
                if dependency == key:
                    r = requests.get(value, timeout=5)
                    with open("repo/{0}".format(key), "w") as file:
                        file.write(r.text)
                    print('Jinja files written!')

    #print('Loading local templates files...')
    env = Environment(loader=FileSystemLoader('repo/'), trim_blocks=True, lstrip_blocks=True)

    try:
        # Load data from YAML into Python dictionary
        answerfile = yaml.load(answers, Loader=yaml.SafeLoader)
        # Load Jinja2 template
        template = env.get_template("render.tmp")
        # Render the template
        rendered_template = template.render(answerfile)

    except Exception as e:
        # If errors, return them to UI.
            emit('render_output', str(e))

    emit('render_output', str(rendered_template))

@socketio.on('getRepo')
def getRepo(form):
    form = json.loads(form['data'])
    
    #github.authorize()
    g.user = None
    if 'user_id' in session:
        get_user = r_app.hgetall(session['user_id'])
        g.user = dotdict(get_user)

    if form.get('selected_repo', None) and form.get('github_user', None):
        repo = form['selected_repo']
        user = form['github_user']

        if GITHUB_ORG:
            org_contents = f'/repos/{GITHUB_ORG}/{repo}/contents/'
            gh_repo_contents = github.get(org_contents)
        else:
            personal_contents = f'/repos/{user}/{repo}/contents/'
            gh_repo_contents = github.get(personal_contents)

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
    if data['device']:
        values = r.hgetall(data['device'])
        device_values = {}
        for x, y in values.items():
            device_values[x.decode("utf-8")] = y.decode("utf-8")

        socketio.emit('foundDevice', device_values)

@socketio.on('deleteDevice')
def deleteDevice(data):
    if data['deleteDevice']:
        r.delete(data['deleteDevice'])
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
    #init_db()
    socketio.run(app, host="0.0.0.0", port=80, debug=True)
