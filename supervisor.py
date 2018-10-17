from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists
from fabric.colors import *
import sys
import string

from muppy_utils import *
from system import get_system_version

"""
Supervisor related tasks
"""

TEMPLATE_CFG_SECTION = """

[supervisor]
#
# If [supervisor] section is defined, then supervisor will be installed and available
#

# [managed_programs] # (Required)
# List of programs that must be running under normal operations. They are defined in appserver
# buildout.cfg using collective.supervisor.recipe.
# Look at: http://github.com/cmorisse/appserver-templatev8 for an example.
# Replace {{supervisor_process_name}} with a list of supervisor 'process_name' separated with ','
#
managed_programs = {{supervisor_process_name}},

"""


class SupervisorConfig:
    pass


def parse_config(config_parser):
    if not config_parser.has_section('supervisor'):
        return None

    # will decompose in case we have to get back on this
    raw_managed_programs = config_parser.get('supervisor', 'managed_programs')
    raw_managed_programs = filter(None, raw_managed_programs.split(','))
    SupervisorConfig.managed_programs = raw_managed_programs

    return SupervisorConfig


@task
def install():
    """Install supervisor using os provided package"""
    # TODO: move to ikez
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    sudo('apt-get install -y supervisor')

    # Next line is required to solve this bug:
    # https://bugs.launchpad.net/ubuntu/+source/supervisor/+bug/1594740
    if env.system.version in ('16.04',):
        sudo('systemctl enable supervisor.service')

    (env.user, env.password,) = env_backup
    return


@task
def generate_config_template():
    """Generate a template [supervisor] section that you can copy paste into muppy config file."""
    print TEMPLATE_CFG_SECTION

def is_supervisor_active():
    """
    Check whether odoo services are registered within supervisor
    :return:
    :rtype:
    """
    if env.supervisor:
        # We use avail as status will return nothing until programs have been started
        command_return = sudo('supervisorctl avail', shell=False, quiet=True, warn_only=True)
        if command_return.succeeded:
            supervisor_list = [filter(None, e.split(' ')) for e in command_return.split('\r\n')]
            if supervisor_list[0]:
                supervisor_set =  set([e[0] for e in supervisor_list])
                if set(env.supervisor.managed_programs) <= supervisor_set:
                    return True

    return False

@task
def stop_services():
    """
    Stop all supervisor managed programs
    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password
    if env.supervisor:
        command_return = sudo('supervisorctl stop %s' % (' '.join(env.supervisor.managed_programs),),
                              quiet=True, warn_only=True)
        if command_return.succeeded:
            (env.user, env.password,) = env_backup
            return True

    (env.user, env.password,) = env_backup
    return False


def get_programs_status():
    """
    :return: a dict where keys are managed programs and values are the state (STOPPED or RUNNING)
    :rtype: dict
    """
    ret_dict = None

    if env.supervisor:
        command_return = sudo('supervisorctl status', shell=False, quiet=True, warn_only=True)
        if command_return.succeeded:
            supervisor_list = [filter(None, e.split(' ')) for e in command_return.split('\r\n')]
            if supervisor_list[0]:
                status_dict = { k[0]: k[1] for k in supervisor_list if k[0] in env.supervisor.managed_programs }
                ret_dict = status_dict
    return ret_dict


@task
def start_services():
    """
    Start all supervisor managed programs
    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password
    if env.supervisor:
        command_return = sudo('supervisorctl start %s' % (' '.join(env.supervisor.managed_programs),),
                              shell=False, quiet=True, warn_only=True)
        if command_return.succeeded:
            (env.user, env.password,) = env_backup
            return True

    (env.user, env.password,) = env_backup
    return False

@task
def activate():
    """Activate supervisor by symlinking appserver generated supervisord.conf

    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password
    v = get_system_version()
    # launch supervisor daemon
    if v == '16.04':
        print blue("Launching supervisor daemon..")
        sudo('systemctl start supervisor')

    # For ubuntu
    # TODO: make this a parameter
    src = "%s/%s/parts/supervisor/supervisord.conf" % (env.customer_path, env.openerp.repository.destination_directory,)
    if not exists(src):
        print red("ERROR: configuration file '%s' does not exist. Unable to activate supervisor." % src)
        sys.exit(1)
    dest = '/etc/supervisor/conf.d/odoo-%s.conf' % env.appserver_id
    sudo('ln -fs %s %s' %  (src, dest,))
    sudo('supervisorctl update')
    (env.user, env.password,) = env_backup
    return True

@task
def deactivate():
    """De-activate supervisor by un-symlinking appserver generated supervisord.conf

    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    # For ubuntu
    # TODO: make this a parameter
    dest = '/etc/supervisor/conf.d/odoo-%s.conf' % env.appserver_id
    sudo('rm %s' %  (dest,))
    sudo('supervisorctl reload')
    (env.user, env.password,) = env_backup
    return True


