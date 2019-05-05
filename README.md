# ConfigPy

### Author:
Nate Mellendorf <br>
https://www.linkedin.com/in/nathan-mellendorf/

## Overview:
This project is the WebUI (frontend) for ConfigPy.
It leverages a Redis DB and the ConfigPY-Node project to build a ZTP-like experience for Juniper equipment.
ConfigPy has a Jijna2/YAML templating feature built in, which allows the user to render config templates stored in a remote repository.
Togeather, the projects goal is to simplify templating and config management for Juniper network equipment.
(It does not work with other vendors at this time.)

#### Additional details
This WebUI is built by a network engineer first, developer second. Some of the code is likely questionable at best.
That said, I try and keep the UI dynamic. The project leverages Python(Flask), Websockets, and JavaScript to push processing to the client and to present results in real time. 

The ConfigPy Hub renders Juniper device details from devices that have checked-in to the Configpy-Node container/server.
I'll likely tie each project together in time with docker-compose, but for now, it's best to run this project along side a Redis DB and the ConfigPy-Node. To simplify this, I've containerized both projects. This allows you to deploy everything you need with Docker.

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

#### Deploy a Redis container
```
docker run --name redis \
-d -p 6379:6379 \
--network production \
--rm redis
```
#### Deploy a ConfigPy-Node container
```
docker run --name configpy-node \
-d -p 9000:9000 \
--network production \
--rm natemellendorf/configpy-node nate P@ssw0rd redis
```
Your Redis and ConfigPy-Node containers would now be connected.
You could confirm this by looking at the logs of the ConfigPy-Node container.
#### Deploy a ConfigPy container
```
docker run --name configpy \
-d -e REDIS_URI=redis \
-p 8080:5000 \
--network production \
--rm natemellendorf/configpy
```
You should be able to browse to the URL of your Docker host to access ConfigPy:
http://DockerHost:8080/
  
#### Configure your Juniper device
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
