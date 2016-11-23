from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists, append
from fabric import colors
import sys
import string
import requests

from muppy_utils import *
"""
System (server) settings and commands
"""

TEMPLATE_CFG_SECTION = """
[system]
#
# locale management
#
# locale is managed using 2 options:
# 1) 'locale' which define the required locale
# 2) 'install' to force muppy to setup locale at the beginning of install.
#     Note that configuration is done only if system locale is different from requested one. Allowed values
#     are valid python expression (True, False, 0, 1).
#
# These options are usefull when deploying on VMs configured for English or even not configured at install
#
# Eg.
# locale=fr_FR.UTF-8
# install = True
#
# Default is:
# locale = None
# install = False
# In that case locale is unmodified whatever value it is.
#
#
#
# SSH keys
#
# List of SSH public keys to add as authorized for created users.
# Ignored if empty. 
# Required AWS EC2
#
# Examples
# admin_ssh_keys =
#    ssh-rsa AAAAdddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd cinder@ello
#    ssh-rsa AAAAB3NzaC1yc2EAAAADAsvvsvvdvbdvbdbvdghenlkhlklkhhkjllhkhlklkhlkhlkhklhkjkjljklllllllllllllllllllllllllllllllllllllllllllllllkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkl cinder@ella
#
#admin_ssh_keys =



"""


class SystemConfig:
    install = False
    locale = None

SUPPORTED_VERSIONS = {
    'ubuntu': ('12.04', '14.04', '16.04',),
    'debian': ('7',),
}


def parse_config(config_parser):
    """
    Parse muppy config file system section
    :param config_parser: A config parser of muppy cfg file.
    :type config_parser: ConfigParser.ConfigParser
    :return: a SystemConfig object
    :rtype : SystemConfig
    """
    if not config_parser.has_section('system'):
        return SystemConfig

    # install
    if config_parser.has_option('system', 'install'):
        raw_value = config_parser.get('system', 'install')
        try:
            SystemConfig.install = eval(raw_value) or False
        except:
            print colors.red("ERROR: [system] section : \"%s\" is not a correct value for 'install' option." % raw_value)
            sys.exit(1)

    # locale is mandatory
    if not config_parser.has_option('system', 'locale') and SystemConfig.install:
        print red("locale options is required in [security] section when install = True!!")
        sys.exit(1)
    raw_locale = config_parser.get('system', 'locale')
    SystemConfig.locale = raw_locale

    # admin_ssh_keys
    if config_parser.has_option('system', 'admin_ssh_keys'):
        raw_admin_ssh_keys = config_parser.get('system', 'admin_ssh_keys')
        raw_admin_ssh_keys = filter(None, raw_admin_ssh_keys.split('\n'))  # split on each line filtering empty ones
        SystemConfig.admin_ssh_keys = raw_admin_ssh_keys
    else:
        SystemConfig.admin_ssh_keys = []

    # distribution
    if config_parser.has_option('system', 'distribution'):
        raw_distrib = config_parser.get('system', 'distribution')
        SystemConfig.distribution = raw_distrib
        if raw_distrib not in ('ubuntu', 'debian',):
            print red("Unsupported Linux Distribution: %s" % raw_distrib)
            sys.exit(1)
    else:
        SystemConfig.distribution = 'ubuntu'


    # version
    if config_parser.has_option('system', 'version'):
        raw_version = config_parser.get('system', 'version')
        SystemConfig.version = raw_version
        if raw_version not in SUPPORTED_VERSIONS[SystemConfig.distribution]:
            print red("Unsupported version: %s for distrib: %s" % (raw_version, raw_distrib,))
            sys.exit(1)
    else:
        SystemConfig.version = '14.04'

    return SystemConfig


@task
def install_prerequisites():
    """Install System Prerequisites."""
    backup_user, backup_password = env.user, env.password
    env.user, env.password = env.root_user, env.root_password
    v = get_version()
    if env.system.version == '16.04':
        sudo('apt-get update --fix-missing')
        sudo("apt-get install -y libsasl2-dev python-dev libldap2-dev libssl-dev")
        sudo("apt-get install -y libz-dev gcc")
        sudo("apt-get install -y libxml2-dev libxslt1-dev")
        sudo("apt-get install -y libpq-dev")
        sudo("apt-get install -y libjpeg-dev libfreetype6-dev liblcms2-dev") 
        sudo("apt-get install -y libopenjpeg5 libopenjpeg-dev") 
        sudo("apt-get install -y libwebp5  libwebp-dev")  
        sudo("apt-get install -y libtiff-dev")  
        sudo("apt-get install -y libyaml-dev")
        sudo("apt-get install -y bzr mercurial git")
        sudo("apt-get install -y curl htop vim tmux")
        sudo("apt-get install -y supervisor")
    
    else:

        sudo('apt-get update --fix-missing')
        sudo("apt-get install -y curl htop vim tmux")
        sudo("apt-get install -y bzr mercurial git")
        sudo("apt-get install -y python-dev libz-dev gcc")
        sudo("apt-get install -y libxml2-dev libxslt1-dev")
        sudo("apt-get install -y libpq-dev")
        sudo("apt-get install -y libldap2-dev libsasl2-dev")
        sudo("apt-get install -y libjpeg-dev libfreetype6-dev liblcms2-dev") 
        # TODO: Rework why do I need it
        #sudo("apt-get liblcms1-dev")
        sudo("apt-get install -y libwebp5  libwebp-dev")  
        sudo("apt-get install -y libtiff-dev")  
        sudo("apt-get install -y libyaml-dev")

    print colors.green("System prerequisites installed.")
    env.user, env.password = backup_user, backup_password
    return


@task
def install_openerp_prerequisites():
    """Install all ubuntu packages required for OpenERP Server (run as root_user)"""
    env.user = env.root_user
    env.password = env.root_password

    v = get_version()
    if v == '16.04':
        sudo('apt install -y virtualenv')
    else:

        # TODO All of this must move to the repository's install.sh
        # TODO: or add some logic to handle different versions behaviour
        #sudo('wget https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py')
        sudo('curl https://bootstrap.pypa.io/ez_setup.py -o ez_setup.py')

        sudo('python ez_setup.py')
        sudo('rm ez_setup.py')

        sudo("easy_install virtualenv==1.11.6")


    print green("OpenERP prerequisites installed.")

@task
def setup_locale(locale=None):
    """
    :[[locale]] - Setup locale defined by [[locale]] parameter or the locale defined in [system] section of muppy cfg file.

    """
    locale = locale or SystemConfig.locale
    if not locale:
        print colors.red("ERROR: Missing required locale parameter.")
        sys.exit(1)

    backup_user, backup_password = env.user, env.password
    env.user, env.password = env.root_user, env.root_password

    if get_version() == '16.04':
        language = locale.split('.')[0]
        ret_val = sudo("locale-gen %s %s" % (language, locale,), quiet=False, warn_only=True)
        if ret_val.failed:
            print colors.red("ERROR: Unable to generate locale '%s'." % locale)
            sys.exit(1)
        ret_val = sudo('update-locale', quiet=False, warn_only=True)
        if ret_val.failed:
            print colors.red("ERROR: Unable to update-locale")
            sys.exit(1)

    else:
        # We check locale is a validone
        ret_val = sudo("locale-gen %s" % locale, quiet=False, warn_only=True)
        if ret_val.failed:
            print colors.red("ERROR: Unable to generate locale '%s'." % locale)
            sys.exit(1)

        language = locale.split('.')[0]
        ret_val = sudo('update-locale LANG="%s" LANGUAGE="%s" LC_ALL="%s" LC_CTYPE="%s"' % (locale, language, locale, locale,), quiet=False, warn_only=True)
        if ret_val.failed:
            print colors.red("ERROR: Unable to update-locale with '%s'." % locale)
            sys.exit(1)

        ret_val = sudo('dpkg-reconfigure -f noninteractive locales', quiet=False, warn_only=True)
        if ret_val.failed:
            print colors.red("ERROR: Unable to 'sudo dpkg-reconfigure -f noninteractive locales'.")
            sys.exit(1)

    print colors.green("Locale '%s' configured." % locale)
    env.user, env.password = backup_user, backup_password
    return


@task
def generate_config_template():
    """Generate a template [system] section to add in a muppy config file."""
    print TEMPLATE_CFG_SECTION

@task
def upgrade():
    """Update and upgrade system (with apt-get)"""
    env.user = env.root_user
    env.password = env.root_password

    sudo("apt-get update --fix-missing")
    sudo("apt-get upgrade -y")
    print green("System updated and upgraded")


@task
def user_get_groups(username, quiet=False):
    env_backup = (env.user, env.password,)

    env.user = env.root_user
    env.password = env.root_password
    groups = sudo('groups %s' % username, warn_only=True, quiet=quiet)

    (env.user, env.password,) = env_backup
    if groups.failed:
        return []
    return groups.split(':')[1].lstrip().split(' ')


@task
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


@task
def user_set_password(username, password):
    env_backup = (env.user, env.password,)
    env.user = env.root_user
    env.password = env.root_password
    sudo("echo '%s:%s' > pw.tmp" % (username, password,), quiet=False)
    sudo("chpasswd < pw.tmp", quiet=False)
    (env.user, env.password,) = env_backup


@task
def user_exists(username):
    return user_search(username) != ''

@task
def get_hostname():
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    hostname = run("hostname", warn_only=True, quiet=True)

    (env.user, env.password,) = env_backup
    return hostname

@task
def user_create(username, password, groups="", system_user=False, quiet=False):
    """:"username","password","group_1;gr2" Create a user belonging to groups. If user exists reset his password and add him into the groups."""
    env_backup = (env.user, env.password)
    
    env.user = env.root_user
    env.password = env.root_password

    # creat euser only it it does not exist
    if not user_search(username):
        if system_user:
            sudo("useradd -m -s /bin/bash --system %s" % (username,), quiet=quiet)
        else:
            sudo("useradd -m -s /bin/bash %s" % (username,), quiet=quiet)

    # manage user group membership
    # check that user is in all requested groups
    group_list = filter(None, groups.split(';'))
    group_list.append(username)
    for group_name in group_list:
        actual_group_list = user_get_groups(username, quiet=quiet)
        if group_name not in actual_group_list:
            sudo('usermod -a -G %s %s' % (group_name, username,), quiet=quiet)

    # We add admin ssh keys to user authorized keys
    sudo("mkdir -p /home/%s/.ssh" % username, user=username)
    for key in SystemConfig.admin_ssh_keys:
        sudo("echo %s >> /home/%s/.ssh/authorized_keys" % (key, username,), user=username)
        #append("/home/%s/.ssh/authorized_keys" % username, key)

    user_set_password(username, password)

    # Generate a ssh key for username if it does not exists
    env.user = username
    env.password = password
    if not exists('~/.ssh/id_rsa'):
        run("ssh-keygen -t rsa -N \"\" -f ~/.ssh/id_rsa", quiet=quiet)

    # download ssh key
    host_name = get_hostname()
    ssh_key_file_name = 'ssh_keys_temp/%s__%s__id_rsa.pub' % (host_name, username,)
    if os.path.exists(ssh_key_file_name):
        os.remove(ssh_key_file_name)
    get('/home/%s/.ssh/id_rsa.pub' % (username,), ssh_key_file_name)
    ssh_key_file = open(ssh_key_file_name)
    ssh_key_string = ssh_key_file.read()


    (env.user, env.password) = env_backup
    return


def user_get_sub_ids(username, quiet=False):
    """Retrieive user sub ids and range"""
    env_backup = (env.user, env.password)

    uid_range_start = sudo("cat /etc/subuid | grep ^%s: | cut -d':' -f2" % username, quiet=quiet)
    uid_range_count = sudo("cat /etc/subuid | grep ^%s: | cut -d':' -f3" % username, quiet=quiet)
    gid_range_start = sudo("cat /etc/subgid | grep ^%s: | cut -d':' -f2" % username, quiet=quiet)
    gid_range_count = sudo("cat /etc/subgid | grep ^%s: | cut -d':' -f3" % username, quiet=quiet)

    (env.user, env.password) = env_backup
    return uid_range_start, uid_range_count, gid_range_start, gid_range_count,


def user_set_ssh_authorized_keys(username, password, ssh_keys, quiet=False):
    """
    Upload a set of ssh keys into a user account.
    Warning: this DOES NOT add the keys but replace all keys with supplied ones !
    :param ssh_keys: list of ssh keys (id_rsa.pub content)
    :type ssh_keys: list
    :param quiet:
    :return:
    """
    env_backup = (env.user, env.password)
    env.user, env.password = username, password
    run("mkdir -p ~./ssh", quiet=quiet)
    run("echo -n > ~/.ssh/authorized_keys", quiet=quiet)
    for ssh_key in ssh_keys:
        run("echo '%s' >> ~/.ssh/authorized_keys" % ssh_key, quiet=quiet)
    (env.user, env.password) = env_backup
    return True

@task
def get_version(format_for='human'):
    """Retrieve system version"""
    env_backup = (env.user, env.password,)
    # we use root_user as it is always defined in config even for lxc
    env.user, env.password = env.root_user, env.root_password

    result = run("python -c \"import platform;print(platform.linux_distribution())\"", quiet=True)
    if result.failed:
        return None

    if format_for == 'human':
        result_as_string = ",".join(eval(result))
        print(result_as_string)
        (env.user, env.password,) = env_backup
        return result_as_string

    (env.user, env.password,) = env_backup
    return eval(result)

