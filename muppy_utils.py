# coding: utf8
import os
from fabric.api import *
from fabric.contrib.files import upload_template, exists, sed
from fabric.colors import *
import ConfigParser
import requests
import datetime
import subprocess
import StringIO


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
    env.user, env.password = env.root_user, env.root_password

    hostname = run("hostname", warn_only=True, quiet=True)

    (env.user, env.password,) = env_backup 
    return hostname

