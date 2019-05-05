import requests
from pprint import pprint

def get_ext_repo(ext_url, *args):

    error_results = dict()

    if 'git' not in ext_url:
        error_results['error'] = 'URL must contain github or gitlab'
        return error_results

    if 'gitlab' in ext_url:
        try:
            words = ext_url.split("/")
            protocol = words[0]
            domain = words[2]
            gitlab_url = '{0}//{1}'.format(protocol, domain)

            findall = '{0}/api/v4/projects/?per_page=100'.format(gitlab_url)

            r = requests.get(findall)
            retuned = r.json()

            for x in retuned:
                #pprint(x['web_url'])
                #pprint(ext_url)
                if x['path_with_namespace'] in ext_url:

                    ext_repo_info = {}

                    #pprint(x)

                    r = requests.get('{0}/api/v4/projects/{1}/repository/tree'.format(gitlab_url, x['id']))
                    d = r.json()
                    #pprint(d)

                    ext_repo_files = {}

                    for path in d:
                        if '.j2' in path['path']:
                            if 'all' in args:
                                ext_repo_files[path['path']] = '{0}/raw/master/{1}'.format(ext_url, path['path'])
                                #print('---- ALL ----')
                            else:
                                filename = path['path'].replace("j2", "yml")
                                for yaml_search in d:
                                    if filename in yaml_search['path']:
                                        ext_repo_files[path['path']] = '{0}/raw/master/{1}'.format(ext_url, path['path'])

                    ext_repo_info['files'] = ext_repo_files

            return ext_repo_info

        except Exception as e:
            error_results['error'] = 'Unable to access GitHub repo...'
            return error_results

    if 'github.com' in ext_url:
        try:
            # Convert user provided url to API url.
            ext_url = ext_url.replace('https://github.com', 'https://api.github.com/repos')

            # With requests, get basic info on repo.
            r = requests.get(ext_url)

            if 'API rate limit exceeded' in r.text:
                error_results['error'] = 'API rate limit exceeded'
                return error_results

            ext_repo_info = r.json()

            # With Requests, get a list of all files in the repo.
            r = requests.get(ext_url + '/contents/')

            d = r.json()
            # Loop over the dictionary we acquired with d, and put interesting info in repo dict.
            ext_repo_files = {}

            for path in d:
                if '.j2' in path['path']:
                    if 'all' in args:
                        ext_repo_files[path['path']] = path['download_url']
                        #print('---- ALL ----')
                    else:
                        filename = path['path'].replace("j2", "yml")
                        for yaml_search in d:
                            if filename in yaml_search['path']:
                                ext_repo_files[path['path']] = path['download_url']

            ext_repo_info['files'] = ext_repo_files

            return ext_repo_info

        except Exception as e:
            error_results['error'] = 'Unable to access GitHub repo...'
            return error_results

if __name__ == '__main__':
    github = 'https://github.com/natemellendorf/tr_templates'
    gitlab = 'http://gitlab/root/awesome'
    test = get_ext_repo(gitlab)
    pprint(test)
