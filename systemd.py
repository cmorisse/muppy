from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists, upload_template
from fabric.colors import *
import sys
import string

import muppy_utils
from system import get_system_version

"""
Systemd related tasks
"""

TEMPLATE_CFG_SECTION = """

[systemd]
#
# If [systemd] section is defined, then systemd will be used to control
# odoo processes.
#

# workers (Required)
# ------------------
# Defines the number of workers launched in multi processing mode.
#workers = {{number}}

"""


class SystemDConfig:
    pass


def parse_config(config_parser):
    if not config_parser.has_section('systemd'):
        return None

    SystemDConfig.workers = config_parser.has_option('systemd', 'workers') and config_parser.get('systemd', 'workers') or "4"
    SystemDConfig.max_cron_threads = config_parser.has_option('systemd', 'max_cron_threads') and config_parser.get('systemd', 'max_cron_threads') or "2"
    SystemDConfig.process_description = config_parser.has_option('systemd', 'process_description') and config_parser.get('systemd', 'process_description') or None
    SystemDConfig.environment = config_parser.has_option('systemd', 'environment') and config_parser.get('systemd', 'environment').split("\n") or []

    return SystemDConfig




@task
def generate_config_template():
    """Generate a template [supervisor] section that you can copy paste into muppy config file."""
    print TEMPLATE_CFG_SECTION


def is_systemd_active():
    """
    Check whether odoo services are registered within supervisor
    :return:
    :rtype:
    """
    if env.systemd:
        return True
    return False

@task
def stop_services():
    """
    Stop all systemd managed programs
    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    unit_filename = "odoo_appserver_%s.service" % env.appserver_id
    sudo("systemctl stop %s" % unit_filename)

    (env.user, env.password,) = env_backup
    return False

@task
def get_status():
    """
    :return: a dict where keys are managed programs and values are the state (STOPPED or RUNNING)
    :rtype: dict
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    unit_filename = "odoo_appserver_%s.service" % env.appserver_id
    sudo("systemctl status %s" % unit_filename)

    (env.user, env.password,) = env_backup
    return False


@task
def restart_services():
    """
    Restart systemd unit
    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password
    
    unit_filename = "odoo_appserver_%s.service" % env.appserver_id
    sudo("systemctl restart %s" % unit_filename)

    (env.user, env.password,) = env_backup
    return False

@task
def start_services():
    """
    Start all supervisor managed programs
    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password
    
    unit_filename = "odoo_appserver_%s.service" % env.appserver_id
    sudo("systemctl start %s" % unit_filename)

    (env.user, env.password,) = env_backup
    return False

@task
def activate():
    """Activate systemd by creating a unit file for appserver process

    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password
    v = get_system_version()['os_version']
    if env.systemd.environment:
        environments = '\n'.join(["Environment=%s" % an_env for an_env in env.systemd.environment])
    else:
        environments = ''
    rendering_context = {
        "process_description": env.systemd.process_description or "%s/%s" % (env.customer_directory, env.openerp.repository.destination_directory),
        "requires_postgres": env.db_host in ('localhost', '127.0.0.1',),
        "base_directory": env.base_directory,
        "customer_directory": env.customer_directory,
        "appserver_directory": env.openerp.repository.destination_directory,
        "workers": env.systemd.workers,
        "max_cron_threads": env.systemd.max_cron_threads,
        "adm_user": env.adm_user,
        "environments": environments
        
    }
    unit_filename = "odoo_appserver_%s.service" % env.appserver_id
    upload_template('./templates/odoo-appserver_id.service.template',
                    "/etc/systemd/system/%s" % unit_filename, 
                    context=rendering_context,
                    use_jinja=True,
                    template_dir=None, 
                    use_sudo=True, 
                    backup=False, 
                    mirror_local_mode=False, 
                    mode=None, 
                    pty=None)
                    #keep_trailing_newline=False, 
                    #temp_dir='')

    sudo("systemctl enable %s" % unit_filename)
    sudo("systemctl daemon-reload")

    (env.user, env.password,) = env_backup
    return True

@task
def deactivate():
    """De-activate systemd by disabling unitfile

    :return:
    :rtype:
    """
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    unit_filename = "odoo_appserver_%s.service" % env.appserver_id
    sudo("systemctl disable %s" % unit_filename)

    (env.user, env.password,) = env_backup
    return True


