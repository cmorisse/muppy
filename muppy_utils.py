# coding: utf8
import os
import ConfigParser
import requests
import datetime
import subprocess
import StringIO

from fabric.api import *
from fabric.contrib.files import exists, sed
from fabric.colors import *
from jinja2 import Template


def user_get_groups(user_name):
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    groups = sudo('groups %s' % user_name, warn_only=True)
    if groups.failed:
        return []

    (env.user, env.password,) = env_backup
    return groups.split(':')[1].lstrip().split(' ')


def user_set_password(user_name, password):
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password
    # set password for adm_user
    sudo("echo '%s:%s' > pw.tmp" % (user_name, password,), quiet=True)
    sudo("sudo chpasswd < pw.tmp", quiet=True)
    sudo("rm pw.tmp", quiet=True)
    (env.user, env.password,) = env_backup
    print green("User \"%s\" password set." % user_name)


def user_search(user_name):
    """
    Search if a user exists
    :type user_name: str looked up username
    :type root_user: str
    :type root_password: str
    :return: id of user
    :rtype: str
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password
    lookup = sudo('id -u %s 2>/dev/null' % user_name, warn_only=True, quiet=True)
    (env.user, env.password,) = env_backup
    return lookup

def user_exists(user_name):
    return user_search(user_name) != ''

def get_hostname():
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    hostname = run("hostname", warn_only=True, quiet=True)

    (env.user, env.password,) = env_backup 
    return hostname

def get_local_hostname():
    import socket
    return socket.gethostname()

def upload_template(template_file_path, remote_path, context={}, use_sudo=False, limit_string='EOF', quiet=False):
    """
    Render and upload a template text file to a remote host.
    Muppy implementation differs from Fabric because it does rely 
    on pure shell with here document rather than SFTP.
    """

    template_file = open(template_file_path)
    template_script = template_file.read()
    template_file.close()

    template = Template(template_script)
    rendered_script = template.render(context)

    if limit_string in rendered_script:
        raise Exception("MuppyTemplate error", "Text to render contains '%s' limit_string. Change text or limit_string" % limit_string)

    template_generation_cmd = """cat > %(remote_path)s <<'%(limit_string)s'
%(rendered_script)s
%(limit_string)s""" % {
        'remote_path': remote_path,
        'limit_string': limit_string,
        'rendered_script': rendered_script,
    }

    runner = sudo if use_sudo else run
    runner(template_generation_cmd, quiet=quiet)

