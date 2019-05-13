# ConfigPy
[![Build Status](https://travis-ci.com/natemellendorf/configpy.svg?branch=master)](https://travis-ci.com/natemellendorf/configpy)
### Author:
Nate Mellendorf <br>
[https://www.linkedin.com/in/nathan-mellendorf/](https://www.linkedin.com/in/nathan-mellendorf/)<br>

## Overview:
This project is for a WebUI (frontend) called ConfigPy.
ConfigPy is a tool that leverages Python to streamline the templating of static text files through Jinja and YAML.

## What does it do?
ConfigPy reaches out via HTTP/HTTPS to a user provided external repository URL. (GitLab or GitHub)
It will then query the repository, and return a list of all .j2 files found in the root directory of master.
It will only display .j2 files that have a matching .yml file. This is a requirment for templating.
ConfigPy will then let the user edit the .yml answer in memory. Once complete, the user can render the template.
That's how it started, anyway. 

The project has grown, and ConfigPy now ties into additional external projects.
It now talks to Redis, ConfigPy-Node, and GitLab.

Once all three are connectected, ConfigPy can be leveraged to render config files from template and push them to GitLab.
ConfigPy-Node is an OpenSSH server, which is configured to terminate Juniper outbound-ssh sessions.
ConfigPy-Node searches for configuraton files in GitLab, and then syncs them with the Juniper devices checking in.
ConfigPy has a WebUI, which displays information about the devices checking-in with ConfigPy-Node.


#### Additional details
This WebUI is built by a network engineer first, developer second. Some of my code is likely questionable.
That said, I try and keep the UI dynamic. The project leverages Flask, Websockets, and JavaScript to push processing to the client and to display results in real time. 

The ConfigPy Hub renders Juniper device details from devices that have checked-in to the Configpy-Node container/server.
I'll likely tie each project together in time with docker-compose, but for now, it's best to run this project along side a Redis DB, ConfigPy-Node, and GitLab.

### Commands:
Update or omit the network flag as needed.
Update the REDIS_URI with the IP address or Docker container name for your Redis server.
```
docker run --name configpy \
-d -e REDIS_URI=redis \
-p 8080:5000 \
--network production \
--rm natemellendorf/configpy
```


### Real world example:
For example, let's deploy everything we need to see this in action.

#### Deploy along side a Redis container
```
docker run --name redis \
-d -p 6379:6379 \
--network production \
--rm redis
```
#### Deploy along side a ConfigPy-Node container
```
docker run --name configpy-node \
-d -p 9000:9000 \
--network production \
--rm natemellendorf/configpy-node nate P@ssw0rd redis
```
Your Redis and ConfigPy-Node containers would now be connected.
You could confirm this by looking at the logs of the ConfigPy-Node container

#### Deploy along side a GitLab container
```
docker run --detach --hostname gitlab.example.com --publish 443:443 --publish 80:80 --publish 22:22 --name gitlab --restart always --volume /srv/gitlab/config:/etc/gitlab --volume /srv/gitlab/logs:/var/log/gitlab --volume /srv/gitlab/data:/var/opt/gitlab gitlab/gitlab-ce:latest
```

#### Deploy the ConfigPy container
```
docker run --name configpy \
-d -e REDIS_URI=redis \
-p 8080:5000 \
--network production \
--rm natemellendorf/configpy
```
You should be able to browse to the URL of your Docker host to access ConfigPy:
http://DockerHost:8080/
  
### How to configure your Juniper device for ConfigPy-Node
Remember to permit this traffic inbound on your mgmt interface.
```
set system services outbound-ssh client test device-id test-srx
set system services outbound-ssh client test services netconf
set system services outbound-ssh client test <DockerHost> port 9000
```

### Review logs from configpy:
ConfigPy logs events automatically.
You can review these at the Docker CLI:
```
docker logs configpy
```
