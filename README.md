# ConfigPy - Standalone

[![Build Status](https://travis-ci.com/natemellendorf/configpy.svg?branch=master)](https://travis-ci.com/natemellendorf/configpy)

### Author:

Nate Mellendorf <br>
[https://www.linkedin.com/in/nathan-mellendorf/](https://www.linkedin.com/in/nathan-mellendorf/)<br>

## Overview:

**ConfigPy - Standalone** is just the rendering portion of the ConfigPy application.
It does not require the configpy-node or a Juniper device to function.

In short, you can leverage standalone to quickly render your Jinja2 templates on the fly.

## Requirments

[GitHub Oauth Application](https://developer.github.com/apps/building-oauth-apps/creating-an-oauth-app/) for ConfigPy.

A working Oauth configuration example:

```
Homepage URL:
http://127.0.0.1/render

Authorization callback URL:
http://127.0.0.1/github-callback
```


## How does it work?

After being supplied with your GitHub OAuth App settings, ConfigPy will search your repositories for readme files that contain the word "configpy". These repositories are expected to have .j2 and .yml template files within their root directory.

Your YAML answer files should be named to match their respective Jinja2 templates.

Example:
- Template: base_ios_config.j2
- Answers: base_ios_config.yml

### Include Statements

Template files can leverage multiple include statements.
This is helpful in creating smaller, reusable Jinja templates.

```
{% include "default_firewall_rules.j2" %}
{% include "aaa_settings.j2" %}
{% include "logging_settings.j2" %}
```

## Deployment:

1. Create a private or organization GitHub OAuth application
2. Clone the repository, change your working directory, and checkout this branch
    ```
    git clone git@github.com:natemellendorf/configpy.git
    cd configpy
    git checkout configpy/standalone
    ```

3. Update the [docker-compose](docker-compose.yml) file with your GitHub Oauth Client ID and Client Secret. 
   - If you're using an OAuth app for your organization, then update and uncomment the GITHUB_ORG environment variable.
   - It's also recommended that you update "NotaSecurePassword" to something more secure.

4. Launch docker-compose to start ConfigPy - Standalone
    ```
    docker-compose up
    ```

5. Browse to http://127.0.0.1:8000/render
