from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    g,
    session,
)

from flask_bootstrap import Bootstrap
from flask_socketio import SocketIO, emit
from flask_github import GitHub
from flask_apscheduler import APScheduler

from nornir import InitNornir
from nornir.plugins.tasks.data import load_yaml
from nornir.plugins.tasks.text import template_file
from nornir.plugins.tasks.networking import napalm_configure, napalm_get
from nornir.plugins.functions.text import print_result
from nornir.plugins.tasks import networking

import yaml
import json
import os
import redis
import time
import logging
import secrets
import requests

from jinja2 import Environment, FileSystemLoader, meta
from datetime import datetime
from get_ext_repo import pushtorepo
from shutil import rmtree
from logging.handlers import RotatingFileHandler
from pprint import pprint

# Needed for SocketIO to actually work...
import eventlet

eventlet.monkey_patch()

# Gather secrets
github_secret = secrets.token_urlsafe(40)
flask_secret = secrets.token_urlsafe(40)

github_oauth = False
github_client_id = os.environ.get("GITHUB_CLIENT_ID", None)
github_client_secret = os.environ.get("GITHUB_CLIENT_SECRET", None)
GITHUB_ORG = os.environ.get("GITHUB_ORG", None)

if github_client_id and github_client_secret:
    github_oauth = True

app = Flask(__name__)
app.config["secret"] = flask_secret
app.config["GITHUB_CLIENT_ID"] = github_client_id
app.config["GITHUB_CLIENT_SECRET"] = github_client_secret
app.config["SECRET_KEY"] = github_secret
bootstrap = Bootstrap(app)
github = GitHub(app)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
socketio = SocketIO(app)

if not os.path.exists("logs"):
    os.mkdir("logs")
file_handler = RotatingFileHandler("logs/configpy.log", maxBytes=1000000, backupCount=10)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    )
)
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info("ConfigPy startup")

# REDIS CONFIG
RD_ADDR = os.environ.get("RD_ADDR", "127.0.0.1")
RD_PW = os.environ.get("RD_PW", "NotaSecurePassword")
RD_PORT = os.environ.get("RD_PORT", 6379)

r = redis.Redis(
    host=RD_ADDR,
    port=RD_PORT,
    db=0,
    decode_responses=True,
    charset="utf-8",
    password=RD_PW,
)
r_app = redis.Redis(
    host=RD_ADDR,
    port=RD_PORT,
    db=1,
    decode_responses=True,
    charset="utf-8",
    password=RD_PW,
)

dbcheck_stat = 0


class dotdict(dict):
    def __getattr__(self, name):
        return self[name]


def current_time():
    current_time = str(datetime.now().time())
    no_sec = current_time.split(".")
    time = no_sec.pop(0)
    return time


def static_error(error):
    new_data = {}
    print(error)
    new_data["event_time"] = current_time()
    new_data["event"] = str(error)
    return new_data


def dbcheck_logic(data, **kwargs):
    # print(kwargs)
    current_time = str(datetime.now().time())
    no_sec = current_time.split(".")
    poll = no_sec.pop(0)
    data["last_poll"] = poll

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
            data["device"] = device_dict
        else:
            data["device"] = ""

    except Exception as e:
        socketio.emit("dsc", {"db_error": str(e)}, broadcast=True)
        return

    if "loopcheck" in kwargs:
        socketio.emit("dsc", data, broadcast=True)

    socketio.emit("dsc", data)


def dbcheck_loop():
    data = {"Get": "devices"}
    with app.test_request_context("/"):
        while True:
            dbcheck_logic(data, loopcheck="yes")
            # Loop delay
            time.sleep(1)


def GitHubAuthRequired(func):
    def authwrapper(*args, **kwargs):
        if github_oauth is False:
            print("Missing GitHub OAuth ID/Secrets!")
            return redirect(url_for("index"))
        elif g.user:
            # print('--- GitHubAuthRequired - g.user---')
            return func(*args, **kwargs)
        else:
            print("Authentication needed")
            return github.authorize(scope="user,repo")

    authwrapper.__name__ = func.__name__
    return authwrapper


@app.before_request
def before_request():
    g.user = None
    if "user_id" in session:
        # print('BEFORE REQUEST')
        # print(session)
        get = r_app.hgetall(session["user_id"])
        g.user = dotdict(get)


@app.after_request
def after_request(response):
    return response


@github.access_token_getter
def token_getter():
    user = g.user
    if user is not None:
        return user.github_access_token


@app.route("/github-callback")
@github.authorized_handler
def authorized(access_token):

    next_url = request.args.get("next") or url_for("render")
    if access_token is None:
        return redirect(next_url)

    user = None
    found_users = r_app.keys()

    # print('access_token')
    # print(access_token)
    # print('- - end access token - - ')

    github_user = github.raw_request("GET", "/user", access_token=access_token)
    github_user = json.loads(github_user.text)
    github_login = github_user["login"]

    if found_users:
        # print('Users were found in DB!')
        # print(f'Users in DB: {found_users}')
        for c_user in found_users:
            current_dict = r_app.hgetall(c_user)
            found_user_name = current_dict.get("github_login")
            found_user_name = found_user_name.strip()
            github_login = github_login.strip()

            print(f"User logging in : {github_login}")
            # print(f'Current User to eval: {found_user_name}')

            if github_login == found_user_name:
                print(f"Found: {github_login}")
                # Update user key in DB
                r_app.hmset(github_login, {"github_access_token": access_token})
                r_app.hmset(github_login, {"github_id": github_user["id"]})
                r_app.hmset(github_login, {"github_login": github_user["login"]})
                r_app.expire(github_login, 900)
                user = r_app.hgetall(c_user)
                break
            else:
                print("No match, checking next user...")
            # print(f'Current: {user}')
    else:
        print("No users in current DB..")

    if user is None:
        # Create new user in DB
        print("Creating new user in DB")
        r_app.hmset(github_login, {"github_access_token": access_token})
        r_app.hmset(github_login, {"github_id": github_user["id"]})
        r_app.hmset(github_login, {"github_login": github_user["login"]})
        r_app.expire(github_login, 900)
        user = r_app.hgetall(github_login)

    # print(f'USER: {user}')

    user = dotdict(user)
    g.user = user
    session["user_id"] = user.github_login

    return redirect(next_url)


@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
def index():
    return redirect(url_for("hub"))


@app.route("/login")
def login():
    if github_oauth and session.get("user_id", None) is None:
        return github.authorize(scope="user,repo")
    else:
        return redirect(url_for("index"))


@app.route("/logout")
def logout():
    if session:
        status = session.pop("user_id", None)

    return redirect(url_for("index"))


@app.route("/user")
@GitHubAuthRequired
def user():
    """
    Auth Example
    """
    return jsonify(github.get("/user"))


@app.route("/hub", methods=["GET", "POST"])
def hub():
    return render_template("hub.html", title="Hub")


@app.route("/render", methods=["GET", "POST"])
@GitHubAuthRequired
def render():

    if GITHUB_ORG:
        result = github.get(
            f"/search/repositories?q=org:{GITHUB_ORG}+configpy+in:readme"
        )
        github_repos = result.get("items", [""])
    else:
        result = github.get(
            f"/search/repositories?q=user:{g.user.github_login}+configpy+in:readme"
        )
        github_repos = result.get("items", [""])

    return render_template(
        "renderform.html", title="Render Template", foundrepos=github_repos
    )


@app.route("/show", methods=["POST"])
def show():
    received = request.get_json()
    answerfile = str(received[0]["value"]).replace(".j2", ".yml")
    r = github.raw_request(method="GET", resource=answerfile)

    return r.text


@app.route("/hub/device/<serialnumber>", methods=["GET"])
def hub_api(serialnumber):
    response = r.hgetall(serialnumber)
    api_request = {}
    for k, v in response.items():
        api_request[k.decode("utf-8")] = v.decode("utf-8")
    response = jsonify(api_request)
    return response


@socketio.on("console")
def test_connect(data):
    current_time = str(datetime.now().time())
    no_sec = current_time.split(".")
    time = no_sec.pop(0)
    data["event_time"] = time
    socketio.emit("console", data)


@socketio.on("hub_console")
def hub_console(data):
    socketio.emit("hub_console", data)


@socketio.on("render_template")
def process(form):

    g.user = None
    if "user_id" in session:
        get_user = r_app.hgetall(session["user_id"])
        if not get_user:
            github.authorize(scope="user,repo")
        g.user = dotdict(get_user)

    form = json.loads(form["data"])
    repo = form.get("selected_repo")
    selected_template = form.get("selected_template")
    answers = form.get("answers")
    user = g.user.github_login
    epoch_time = str(time.time())

    emit("progress_bar", {"status": "secondary", "progress": 5})

    if "---" not in answers:
        app.logger.info(f"Answers must begin with ---")
        emit("render_console", "Answers must begin with ---")
        emit("progress_bar", {"status": "danger", "progress": 100})
        emit("render_output", f"Answers must begin with ---")
        return

    if GITHUB_ORG:
        org_selected_template = (
            f"/repos/{GITHUB_ORG}/{repo}/contents/{selected_template}"
        )
        app.logger.info(f"Attempting to GET: {org_selected_template}")
        emit("render_console", f"Attempting to GET: {org_selected_template}")
        template_file = github.raw_request(
            method="GET",
            resource=org_selected_template,
            access_token=get_user["github_access_token"],
            headers={"Accept": "application/vnd.github.v3.raw"},
        )
    else:
        personal_selected_template = (
            f"/repos/{user}/{repo}/contents/{selected_template}"
        )
        app.logger.info(f"Attempting to GET: {personal_selected_template}")
        emit("render_console", f"Attempting to GET: {personal_selected_template}")
        template_file = github.raw_request(
            method="GET",
            resource=personal_selected_template,
            access_token=get_user["github_access_token"],
            headers={"Accept": "application/vnd.github.v3.raw"},
        )

    emit("progress_bar", {"status": "secondary", "progress": 10})

    working_dir = f"repo/{epoch_time}"

    try:
        os.mkdir(working_dir)
    except OSError:
        app.logger.error(f"Creation of the directory {epoch_time} failed")
        emit("render_console", f"Creation of the directory {epoch_time} failed")
        emit("progress_bar", {"status": "danger", "progress": 100})
        return
    except Exception as e:
        app.logger.error(f"Unknown Exception: {e}")
        emit("render_console", f"Unknown Exception: {e}")
        emit("progress_bar", {"status": "danger", "progress": 100})
        return
    else:
        app.logger.info(f"Successfully created the directory {epoch_time}")
        emit("render_console", f"Successfully created the directory {epoch_time}")
        emit("progress_bar", {"status": "secondary", "progress": 20})

    local_template = f"repo/{epoch_time}/render.tmp"
    app.logger.info(f"Attempting to write template to: {local_template}")
    emit("render_console", f"Attempting to write template to: {local_template}")
    with open(local_template, "w") as file:
        file.write(template_file.text)

    emit("progress_bar", {"status": "secondary", "progress": 30})

    env = Environment(
        loader=FileSystemLoader("repo/"), trim_blocks=True, lstrip_blocks=True
    )
    ast = env.parse(template_file.text)
    dependencies = list(meta.find_referenced_templates(ast))

    emit("progress_bar", {"status": "secondary", "progress": 40})

    if dependencies:
        app.logger.info(f"Jinja Dependancies found")
        emit("render_console", f"Jinja Dependancies found")

        if GITHUB_ORG:
            app.logger.info(f"Gathering Org template dependancies")
            emit("render_console", f"Gathering Org template dependancies")
            org_contents = f"/repos/{GITHUB_ORG}/{repo}/contents/"
            repo_contents = github.get(org_contents)

        else:
            app.logger.info(f"Gathering Personal template dependancies")
            emit("render_console", f"Gathering Personal template dependancies")
            personal_contents = f"/repos/{user}/{repo}/contents/"
            repo_contents = github.get(personal_contents)

        emit("progress_bar", {"status": "secondary", "progress": 50})

        ext_repo_files = {}

        for item in repo_contents:
            if ".j2" in item["path"]:
                ext_repo_files[item["path"]] = item["download_url"]

        emit("progress_bar", {"status": "secondary", "progress": 60})

        l_index = 0

        for key, value in ext_repo_files.items():
            for dependency in dependencies:
                if dependency == key:
                    l_index += 1
                    current = l_index / 3
                    app.logger.info(f"Dependency number: {60 + current}")
                    emit("render_console", f"Dependency number: {60 + current}")

                    emit(
                        "progress_bar",
                        {"status": "secondary", "progress": 60 + current},
                    )

                    r = requests.get(value, timeout=5)
                    dependency_file = f"repo/{epoch_time}/{key}"

                    app.logger.info(f"Dependency name: {dependency_file}")
                    emit(
                        "render_console",
                        f"Attempting to write dependency: {dependency_file}",
                    )

                    with open(dependency_file, "w") as file:
                        file.write(r.text)

                    if os.path.exists(dependency_file):
                        app.logger.info(f"Dependency written successfully")
                        emit("render_console", f"File written successfully")
                    else:
                        app.logger.info(f"Fail: Dependency was written but not found")
                        emit(
                            "render_console",
                            f"Fail: Dependency was written but not found",
                        )
                        return

    app.logger.info(f"All required files gathered!")
    emit("render_console", f"All required files gathered!")

    emit("progress_bar", {"status": "secondary", "progress": 90})

    template_wd = f"repo/{epoch_time}/"
    app.logger.info(f"Setting template directory to: {template_wd}")
    emit("render_console", f"Setting template directory to: {template_wd}")
    env = Environment(
        loader=FileSystemLoader(template_wd), trim_blocks=True, lstrip_blocks=True
    )

    try:
        # Load data from YAML into Python dictionary
        answerfile = yaml.load(answers, Loader=yaml.SafeLoader)
        # Load Jinja2 template
        template = env.get_template("render.tmp")
        # Render the template
        rendered_template = template.render(answerfile)

        app.logger.info(f"Render Complete!")
        emit("render_console", f"Render Complete!")
        emit("render_output", str(rendered_template))
        emit("progress_bar", {"status": "success", "progress": 100})

    except Exception as e:
        # If errors, return them to UI.
        app.logger.info(f"Error Rendering: {e}")
        emit("progress_bar", {"status": "danger", "progress": 100})
        emit("render_console", f"Error Rendering: {e}")
        emit("render_output", str(e))

    try:
        rmtree(working_dir)
    except Exception as e:
        app.logger.error(f"Deletion of the directory {working_dir} failed")
        emit("render_console", f"Deletion of the directory {working_dir} failed")

        return
    else:
        app.logger.info(f"Successfully deleted the directory {working_dir}")
        emit("render_console", f"Successfully deleted the directory {working_dir}")


@socketio.on("getRepo")
def getRepo(form):
    form = json.loads(form["data"])

    # github.authorize()
    g.user = None
    if "user_id" in session:
        get_user = r_app.hgetall(session["user_id"])
        if not get_user:
            github.authorize(scope="user,repo")
        g.user = dotdict(get_user)

    if form.get("selected_repo", None) and form.get("github_user", None):
        repo = form["selected_repo"]
        user = form["github_user"]

        emit("render_console", f"Requesting User: {user}")
        emit("render_console", f"Repo to search: {repo}")

        if GITHUB_ORG:
            org_contents = f"/repos/{GITHUB_ORG}/{repo}/contents/"
            gh_repo_contents = github.get(org_contents)
        else:
            personal_contents = f"/repos/{user}/{repo}/contents/"
            gh_repo_contents = github.get(personal_contents)

        ext_repo_files = {}
        ext_repo_info = {}

        for path in gh_repo_contents:
            if ".j2" in path["path"]:
                filename = path["path"].replace("j2", "yml")
                for yaml_search in gh_repo_contents:
                    if filename in yaml_search["path"]:
                        emit("render_console", f"Templates found: {path['path']}")
                        ext_repo_files[path["path"]] = path["download_url"]

        ext_repo_info["files"] = ext_repo_files

        emit("repoContent", ext_repo_info)


@socketio.on("getDevice")
def getDevice(data):
    if data["device"]:
        values = r.hgetall(data["device"])
        device_values = {}
        for x, y in values.items():
            device_values[x.decode("utf-8")] = y.decode("utf-8")

        socketio.emit("foundDevice", device_values)


@socketio.on("deleteDevice")
def deleteDevice(data):
    if data["deleteDevice"]:
        r.delete(data["deleteDevice"])
        socketio.emit("deletedDevice", f'Removed: {data["deleteDevice"]}')


@socketio.on("dsc")
def dsc(data):
    # define global var
    global dbcheck_stat

    # If var is 0, then start the while loop to check DB.
    # It's important to only run this loop once, else, each new user starts a new run.
    if dbcheck_stat == 0:
        # update the global var so the loop is not run again.
        dbcheck_stat = 1
        # Start the loop
        app.apscheduler.add_job(func=dbcheck_loop, trigger="date", id="loop")

    # If the loops been started but this is a new user request, run the loop logic once.
    # That way, the users web request completes with valid data.
    # Else, the page will load with no data (until the loop runs.)
    dbcheck_logic(data)




@socketio.on("nornirPush")
def configureDevice(data):
    answers = yaml.safe_dump(json.loads(data.get("data", '{}')))
    answers_dict = json.loads(data.get("data", '{}'))
    config = answers_dict["config"]

    template_wd = f"repo/"

    app.logger.info(f"Setting template directory to: {template_wd}")
    emit("render_console", f"Setting template directory to: {template_wd}")

    env = Environment(
        loader=FileSystemLoader(template_wd), trim_blocks=True, lstrip_blocks=True
    )

    try:
        # Load data from YAML into Python dictionary
        answerfile = yaml.load(answers, Loader=yaml.SafeLoader)
        # Load Jinja2 template
        template = env.get_template("host.j2")
        # Render the template
        rendered_template = template.render(answerfile)

        app.logger.info(f"Render Complete!")
        emit("nornir_console", f"Render Complete!")
        emit("nornir_console", str(rendered_template))
        emit("progress_bar", {"status": "success", "progress": 100})

    except Exception as e:
        # If errors, return them to UI.
        app.logger.info(f"Error Rendering: {e}")
        emit("progress_bar", {"status": "danger", "progress": 100})
        emit("nornir_console", f"Error Rendering: {e}")
        emit("nornir_console", str(e))
        return

    #print(rendered_template)

    try:
        epoch_time = str(time.time())
        working_dir = f"repo/{epoch_time}"
        os.mkdir(working_dir)
    except OSError:
        app.logger.error(f"Creation of the directory {epoch_time} failed")
        emit("nornir_console", f"Creation of the directory {epoch_time} failed")
        emit("nornir_progress_bar", {"status": "danger", "progress": 100})
        return
    except Exception as e:
        app.logger.error(f"Unknown Exception: {e}")
        emit("nornir_console", f"Unknown Exception: {e}")
        emit("nornir_progress_bar", {"status": "danger", "progress": 100})
        return
    else:
        app.logger.info(f"Successfully created the directory {epoch_time}")
        emit("nornir_console", f"Successfully created the directory {epoch_time}")
        emit("nornir_progress_bar", {"status": "secondary", "progress": 20})

    # Create host.yaml for Nornir
    try:
        with open(f"{working_dir}/host.yaml", "w") as file:
            file.write(rendered_template)

    except OSError:
        app.logger.error(f"Failed to create: {working_dir}/host.yaml")
        emit("nornir_console", f"Failed to create: {working_dir}/host.yaml")
        emit("nornir_progress_bar", {"status": "danger", "progress": 100})
        return

    except Exception as e:
        app.logger.error(f"Unknown Exception: {e}")
        emit("nornir_console", f"Unknown Exception: {e}")
        emit("nornir_progress_bar", {"status": "danger", "progress": 100})
        return

    finally:
        app.logger.info(f"Successfully created: {working_dir}/host.yaml")
        emit("nornir_console", f"Successfully created: {working_dir}/host.yaml")
        emit("nornir_progress_bar", {"status": "secondary", "progress": 20})


    # Init Nornir
    nr = InitNornir(
    core={"num_workers": 2},
    inventory={
        "plugin": "nornir.plugins.inventory.simple.SimpleInventory",
        "options": {
            "host_file": f"{working_dir}/host.yaml"
            }
        }
    )

    # Create NAPALM config update task for Nornir
    def update_config(task, **kwargs):
    
        app.logger.info(f"Entered update task")
        config = kwargs["config"]

        r = task.run(
            name="Loading config onto device...",
            task=napalm_configure,
            configuration=config
        )

        return r

    # Push config to device
    r = nr.run(update_config, config=config)

    # Return results
    app.logger.info(f'{r["device"]}')
    emit("nornir_console", f'{r["device"]}')

    # Cleanup our workspace
    try:
        rmtree(working_dir)
    except Exception as e:
        app.logger.error(f"Deletion of the directory {working_dir} failed")
        emit("nornir_console", f"Deletion of the directory {working_dir} failed")

        return
    else:
        app.logger.info(f"Successfully deleted the directory {working_dir}")
        emit("nornir_console", f"Successfully deleted the directory {working_dir}")
    
    # FIN
    socketio.emit("nornir_result", "Processing...")
    socketio.emit("nornir_result", data)



@socketio.on("gitlabPush")
def gitlabPush(data):
    data = json.loads(data)

    if (
        data["clientID"]
        and data["repo_auth_token"]
        and data["serialNumber"]
        and data["device_config"]
        and data["repo_uri"]
    ):

        for node, serialNumber in data["serialNumber"].items():
            if serialNumber:
                print(f"Pushing node: {node} - serial: {serialNumber}")
                new_data = pushtorepo(
                    data=data, REDIS_URI=REDIS_URI, serialNumber=serialNumber, node=node
                )
                socketio.emit("git_console", new_data)
            else:
                new_data = dict()
                new_data["event_time"] = current_time()
                new_data["event"] = f"Ignored: {node}"
                socketio.emit("git_console", new_data)

    else:
        new_data = dict()
        new_data["event_time"] = current_time()
        new_data["event"] = "The form submitted is missing values."
        socketio.emit("git_console", new_data)


@socketio.on("connect")
def connect():
    print("Client connected!")


@socketio.on("disconnect")
def disconnect():
    print("Client disconnected")


if __name__ == "__main__":
    # init_db()
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
