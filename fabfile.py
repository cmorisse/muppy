# coding: utf8
import os
from fabric.api import *
from fabric.contrib.files import upload_template, exists, sed
from fabric.colors import *
from fabric import colors
import ConfigParser
import requests
import datetime
import subprocess
import StringIO

import muppy_utils
from bitbucket import BitbucketRepository
from gitlab_driver import GitlabRepository

from muppy_magento import *
import vagrant
import postgresql
import openerp
import security
import system  # And no system is not a python module ; it's a muppy one
import lxc

__version__ = '0.2.9'

# TODO: Installation JasperReport Server

if not env.get('config_file', False):
    print blue("Launching muppy version %s" % __version__)
    print ""
    print red("ERROR: config_file parameter is mandatory.")
    print red("Please launch with:")
    print red("  fab --set config_file=your_file.cfg")
    print 
    exit(0)


config_parser = ConfigParser.ConfigParser()
config_parser.readfp(open(env.config_file))
if not config_parser.has_option('env', 'muppy_version') or not __version__.startswith(config_parser.get('env', 'muppy_version')):
    print red("ERROR: unsupported config_file version ; version 0.2 is required")
    exit(0)


if config_parser.has_option('env', 'linux_distribution'):
    env.linux_distribution = config_parser.get('env', 'linux_distribution')
else:
    env.linux_distribution = 'ubuntu'

if config_parser.has_option('env', 'hosts'):
    env.hosts = config_parser.get('env', 'hosts').split(',')
env.root_user = config_parser.get('env', 'root_user')
env.root_password = config_parser.get('env', 'root_password')


env.adm_user = (config_parser.has_option('env', 'adm_user') and config_parser.get('env', 'adm_user')) or env.root_user
env.adm_password = (config_parser.has_option('env', 'adm_password') and config_parser.get('env', 'adm_password')) or env.root_password
env.adm_user_is_sudoer = (config_parser.has_option('env', 'adm_user_is_sudoer') and config_parser.getboolean('env', 'adm_user_is_sudoer')) or False


env.db_user = (config_parser.has_option('env', 'db_user') and config_parser.get('env', 'db_user')) or env.adm_user
env.db_password = (config_parser.has_option('env', 'db_password') and config_parser.get('env', 'db_password')) or env.adm_password
env.db_host = (config_parser.has_option('env', 'db_host') and config_parser.get('env', 'db_host')) or 'localhost'
env.db_port = (config_parser.has_option('env', 'db_port') and config_parser.get('env', 'db_port')) or '5432'


env.customer_directory = (config_parser.has_option('env', 'customer_directory') and config_parser.get('env', 'customer_directory')) or 'muppy'

env.customer_path = "/opt/openerp/%s" % (env.customer_directory,)

env.openerp_admin_password = (config_parser.has_option('env', 'openerp_admin_password') and config_parser.get('env', 'openerp_admin_password')) or 'admin'

env.backup_directory = (config_parser.has_option('env', 'backup_directory') and config_parser.get('env', 'backup_directory')) or '/opt/openerp/backups'
env.muppy_transactions_directory = (config_parser.has_option('env', 'muppy_transactions_directory') and config_parser.get('env', 'muppy_transactions_directory')) or '/opt/openerp/muppy_transactions'
env.muppy_buffer_directory = (config_parser.has_option('env', 'muppy_buffer_directory') and config_parser.get('env', 'muppy_buffer_directory')) or '/opt/openerp/muppy_buffer'
env.test_database_name = (config_parser.has_option('env', 'test_database_name') and config_parser.get('env', 'test_database_name')) or env.customer_directory + '_dev'
env.addons_list = (config_parser.has_option('env', 'addons_list') and config_parser.get('env', 'addons_list')) or 'all'


#
# Magento
if config_parser.has_section('magento'):
    env.magento = magento_parse_config(config_parser)
#
# Vagrant
if config_parser.has_section('vagrant'):
    env.vagrant = vagrant.parse_config(config_parser)

#
# PostgreSQL
env.postgresql = postgresql.parse_config(config_parser)

#
# Security
env.security = security.parse_config(config_parser)

#
# system
env.system = system.parse_config(config_parser)

#
# lxc
env.lxc = lxc.parse_config(config_parser)


# TODO: eval root, adm, pg, postgres, user and password from os.environ

class _AppserverRepository:
    enabled = False
    server_type = 'bitbucket'


if config_parser.has_section('appserver_repository'):
    _AppserverRepository.server_type = config_parser.get('appserver_repository', 'server_type')
    if _AppserverRepository.server_type not in ('gitlab', 'bitbucket'):
        print red("Error: Unsupported value for appserver_repository.server_type : %s" % _AppserverRepository.server_type)
        exit(-1)
    _AppserverRepository.appserver_url = (config_parser.has_option('appserver_repository', 'appserver_url') and config_parser.get('appserver_repository', 'appserver_url')) or "git git@bitbucket.org:cmorisse/appserver-templatev7.git"

    str_to_eval = config_parser.get('appserver_repository', 'user')
    _AppserverRepository.user = eval(str_to_eval, {'os': os})

    str_to_eval = config_parser.get('appserver_repository', 'password')
    _AppserverRepository.password = eval(str_to_eval, {'os': os})

    if _AppserverRepository.server_type == 'bitbucket':
        _AppserverRepository.repository = BitbucketRepository(_AppserverRepository.user,
                                                              _AppserverRepository.password,
                                                              _AppserverRepository.appserver_url,
                                                              env.customer_path)
    elif _AppserverRepository.server_type == 'gitlab':
        _AppserverRepository.repository = GitlabRepository(_AppserverRepository.user,
                                                           _AppserverRepository.password,
                                                           _AppserverRepository.appserver_url,
                                                           env.customer_path)

    # we build a list of others private repositories
    _AppserverRepository.other_private_repo_urls = (config_parser.has_option('appserver_repository', 'other_private_repo_urls') and config_parser.get('appserver_repository', 'other_private_repo_urls')) or ''
    repositories_url_list = [] or (_AppserverRepository.other_private_repo_urls and _AppserverRepository.other_private_repo_urls.split('\n'))
    repositories_list = []
    for repository_url in repositories_url_list:
        if _AppserverRepository.server_type == 'bitbucket':
            repository = BitbucketRepository(_AppserverRepository.user,
                                             _AppserverRepository.password,
                                             repository_url,
                                             env.customer_path)
        elif _AppserverRepository.server_type == 'gitlab':
            repository = GitlabRepository(_AppserverRepository.user,
                                          _AppserverRepository.password,
                                          repository_url,
                                          env.customer_path)
        #elif _AppserverRepository.server_type == 'github':
        else:
            raise exception("Repository server type '%s' not implemented" % _AppserverRepository.server_type)

        repositories_list.append(repository)
    _AppserverRepository.other_private_repositories = repositories_list\

    _AppserverRepository.enabled = True
    env.openerp = _AppserverRepository


@task
def mupping(root_user=env.root_user, root_password=env.root_password):
    """Mup"ping": try to run ls over ssh"""
    env.user = root_user
    env.password = root_password
    run("ls /") 
    return


#
# PostgreSQL Installation related functions
#
@task
def pg_install_server():
    """Install Postgresql Server and CLI Client."""
    env.user = env.root_user
    env.password = env.root_password

    sudo('apt-get update --fix-missing')
    sudo('apt-get install -y postgresql graphviz postgresql-client')
    print green("PosgreSQL server and client installed.")

@task
def pg_create_openerp_user(pg_user=env.db_user, pg_password=env.db_password):
    """Create a Postgres User for OpenERP Server"""
    env.user = env.root_user
    env.password = env.root_password

    sudo( """su postgres -c 'echo "CREATE ROLE %s WITH LOGIN SUPERUSER CREATEDB NOCREATEROLE ENCRYPTED PASSWORD '"'"'%s'"'"' ;" | psql ' """ % (pg_user, pg_password) )
    print green("PosgreSQL %s user created." % pg_user)

@task
def pg_allow_remote_access_for_EVERYONE():
    """Configure Postgres to allow remote network connection from any host. WARNING High Security Risk"""
    env.user = env.root_user
    env.password = env.root_password

    # TODO check ubuntu version
    # TODO check postgres version 
    sudo("""su postgres -c 'echo "# Generated by mup.py">> /etc/postgresql/9.1/main/postgresql.conf'""")
    sudo("""su postgres -c 'echo "listen_addresses = '"'"'*'"'"' ">> /etc/postgresql/9.1/main/postgresql.conf'""")

    sudo("""su postgres -c 'echo "# Generated by mup.py" >> /etc/postgresql/9.1/main/pg_hba.conf'""")
    sudo("""su postgres -c 'echo "host     all             all             0.0.0.0/0               md5" >> /etc/postgresql/9.1/main/pg_hba.conf'""")
    sudo("service postgresql restart")
    print green("PosgreSQL is now reachable from remote network.")


@task
def pg_install_db_server(pg_user=env.db_user, pg_password=env.db_password):
    """Install PostgreSQL server then create database user"""
    pg_install_server()
    pg_create_openerp_user(pg_user=pg_user, pg_password=pg_password)

#
# VMware Tools Installation (sucks)
#
@task
def sys_install_vmware_tools():
    """VMWare Tools Installation (requires the tools ISO to be mounted)"""
    env.user = env.root_user
    env.password = env.root_password

    # TODO: Test for Hypervisor Version, download tools, install them then clean
    print
    print red("VMware Tools Installation")
    print
    print red("  First, check that VMWare Tools ISO Image is connected to the VM.  But don't mount it !!!")
    print
    raw_input("  Press Enter to continue or CTRL-C to abandon.")
    sudo('mkdir -p /mnt/cdrom')
    sudo('mount /dev/cdrom /mnt/cdrom')
    sudo('cp /mnt/cdrom/VM* ~')
    sudo('tar -zxf VM*')
    sudo('apt-get install -y linux-headers-server build-essential')
    sudo('cd vmware-tools-distrib && ./vmware-install.pl -d')

#
# System related tasks
#

@task
def get_system_version(format_for='human'):
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

@task
def sys_install_openerp_prerequisites():
    """Install all ubuntu packages required for OpenERP Server (run as root_user)"""
    env.user = env.root_user
    env.password = env.root_password


    # TODO All of this must move to the repository install.sh
    # TODO: or add some logic to handle different versions behaviour
    #sudo('wget https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py')
    sudo('curl https://bootstrap.pypa.io/ez_setup.py -o ez_setup.py')

    sudo('python ez_setup.py')
    sudo('rm ez_setup.py')

    sudo("easy_install virtualenv==1.11.6")

    sudo("apt-get install -y python-dev libz-dev")
    sudo("apt-get install -y libxml2-dev libxslt1-dev")
    sudo("apt-get install -y libpq-dev")
    sudo("apt-get install -y libldap2-dev libsasl2-dev")
    sudo("apt-get install -y libjpeg-dev libfreetype6-dev liblcms2-dev liblcms1-dev libwebp-dev libtiff-dev")
    sudo("apt-get install -y libyaml-dev")
    sudo("apt-get install -y bzr mercurial git")
    sudo("apt-get install -y curl htop vim tmux")
    print green("OpenERP prerequisites installed.")

def get_sshkey_name():
    return 'muppy:%s@%s' % (env.adm_user, system.get_hostname(),)

def download_ssh_key():
    # download ssh key
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password
    result = run('cat /home/%s/.ssh/id_rsa.pub' % env.adm_user )
    env.user, env.password = env_backup
    return result

@task
def update_ssh_key_on_private_repositories(sshkey_string=None):
    """Update ssh-key on all private repositories"""
    env.user = env.adm_user
    env.password = env.adm_password

    if not sshkey_string:
        sshkey_string = download_ssh_key()

    if env.openerp.repository.update_deployment_key(get_sshkey_name(), sshkey_string):
        print green("Deployment key (%s) successfully added to %s repository \"%s\"." % (get_sshkey_name(),
                                                                                         env.openerp.server_type,
                                                                                         env.openerp.repository.name))
    else:
        print red("Error: Unable to update deployment key on %s repository: %s/%s" % (env.openerp.repository.owner,
                                                                                      env.openerp.server_type,
                                                                                      env.openerp.repository.name,))
    # then we update keys on others private repositories
    for repository in env.openerp.other_private_repositories:
        if repository.update_deployment_key(get_sshkey_name(), sshkey_string):
            print green("Deployment key (%s) successfully uploaded to bitbucket repository %s/%s." % (get_sshkey_name(),
                                                                                                      repository.owner,
                                                                                                      repository.name,))
        else:
            print red("Error: Unable to update deployment key (%s) for bitbucket repository :%s/%s" % (get_sshkey_name(),
                                                                                                       repository.owner,
                                                                                                       repository.name))

@task
def sys_create_openerp_user():
    """Create openerp admin user"""
    env.user = env.root_user
    env.password = env.root_password


    # create adm_user if it does not exists
    if not system.user_search(env.adm_user):
        sudo("useradd -m -s /bin/bash --system %s" % (env.adm_user,))

    # manage adm_user sudo membership
    if env.adm_user_is_sudoer:
        # we remove our retricted rights file as it may conflict with
        # next operation where we add adm_user in sudo group
        if exists('/etc/sudoers.d/muppy', use_sudo=True):
            sudo("rm /etc/sudoers.d/muppy")

        # add adm_user to sudo group
        if not 'sudo' in system.user_get_groups(env.adm_user):
            sudo('usermod -a -G sudo %s' % env.adm_user)

    else:
        if 'sudo' in system.user_get_groups(env.adm_user):
            sudo('deluser %s sudo' % env.adm_user)

        # We grant right manage openerp services (classic and gunicorn) to adm_user group. We use:
        #echo "%openerp ALL = /etc/init.d/openerp-server,/etc/init.d/gunicorn-openerp" > /etc/sudoers.d/muppy
        #chmod 0440 /etc/sudoers.d/muppy
        # We always overwrite the file
        sudo("echo \"%s ALL = /etc/init.d/openerp-server,/etc/init.d/gunicorn-openerp\" > /etc/sudoers.d/muppy" % env.adm_user)
        sudo("chmod 0440 /etc/sudoers.d/muppy")

    system.user_set_password(env.adm_user, env.adm_password)

    # Generate a ssh key for adm_user if it does not exists
    env.user = env.adm_user
    env.password = env.adm_password
    if not exists('~/.ssh/id_rsa'):
        run("ssh-keygen -t rsa -N \"\" -f ~/.ssh/id_rsa")

    # download ssh key
    ssh_key_string = download_ssh_key()

    # update ssh-key on all private repositories
    update_ssh_key_on_private_repositories(ssh_key_string)

@task
def sys_create_customer_directory(root_user=env.root_user, root_password=env.root_password):
    """Create Customer directory (/opt/openerp/<customer_directory>) owned by adm_user"""
    # Create :
    #   - Customer directory (/opt/openerp/<customer_directory>) that will hold all subprojects related to this server.
    #  Grant rights only to adm_user (run as root_user)
    env.user = root_user
    env.password = root_password
    sudo("mkdir -p %s" % (env.customer_path,))
    sudo("chmod 755 %s" % (env.customer_path,))
    sudo("chown -R %s: %s" % (env.adm_user, env.customer_path,))
    print green("Directory %s created." % env.customer_path )

@task
def sys_create_log_directory(root_user=env.root_user, root_password=env.root_password):
    """Create openerp server log directory ( /var/log/openerp ) and grant rights to adm_user""" 
    # Create :
    #   - Openerp log directory
    #  Grant rights only to adm_user (run as root_user)
    env.user = root_user
    env.password = root_password

    sudo('mkdir -p /var/log/openerp', quiet=True)
    sudo('chown -R %s:root /var/log/openerp' % (env.adm_user,), quiet=True)
    sudo('chmod 775 /var/log/openerp', quiet=True)
    print green("OpenERP log directory: \"/var/log/openerp/\" created (owner: %s)." % env.adm_user)

@task
def sys_create_backup_directory(root_user=env.root_user, root_password=env.root_password):
    """Create Muppy backup directory"""
    env.user = root_user
    env.password = root_password

    sudo('mkdir -p %s' % env.backup_directory, quiet=True)

    sudo('chown -R %s: %s' % (env.adm_user, env.backup_directory,), quiet=True)
    sudo('chmod 755 %s' % env.backup_directory, quiet=True)
    print green("Muppy backup directory: \"%s\" created." % env.backup_directory)

@task
def sys_create_buffer_directory(root_user=env.root_user, root_password=env.root_password):
    """Create Muppy buffer directory"""
    env.user = root_user
    env.password = root_password

    sudo('mkdir -p %s' % env.muppy_buffer_directory, quiet=True)
    sudo('chown -R %s: %s' % (env.adm_user, env.muppy_buffer_directory,), quiet=True)
    sudo('chmod 755 %s' % env.muppy_buffer_directory, quiet=True)
    print green("Muppy buffer directory: \"%s\" created." % env.muppy_buffer_directory)

@task
def sys_create_muppy_transactions_directory(root_user=env.root_user, root_password=env.root_password):
    """Create Muppy transactions directory"""
    env.user = root_user
    env.password = root_password

    sudo('mkdir -p %s' % env.muppy_transactions_directory, quiet=True)
    sudo('chown -R %s: %s' % (env.adm_user, env.muppy_transactions_directory,), quiet=True)
    sudo('chmod 755 %s' % env.muppy_transactions_directory, quiet=True)
    print green("Muppy transactions directory: \"%s\" created." % env.muppy_transactions_directory)


#
# OpenERP related tasks
#
def sed_escape(s):
    """Utility to preserve special characters in password during sed(ing) of buildout.cfg"""
    t1 = s.replace("\\", "\\\\")
    t2 = t1.replace("/", "\\/")
    t3 = t2.replace("&", "\&")
    return t3


@task
def generate_buildout_cfg(buildout_cfg_path, base_template_name="buildout.cfg.template"):
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    generate_buildout_content_cmd = """cat > %s <<EOF
[buildout]
extends = %s
[openerp]
options.admin_passwd = %s
options.db_user = %s
options.db_password = %s
EOF""" % (buildout_cfg_path, base_template_name, env.openerp_admin_password, env.db_user, env.db_password,)

    run(generate_buildout_content_cmd)
    (env.user, env.password,) = env_backup 
    return

@task
def openerp_clone_appserver(adm_user=env.adm_user, adm_password=env.adm_password):
    """Clone an appserver repository and setup buildout.cfg"""
    env.user = adm_user
    env.password = adm_password

    # update known_host (remove then add hostname)
    if _AppserverRepository.repository.protocol == 'ssh':
        if exists("~/.ssh/known_hosts"):
            # Remove host from known_hosts file
            run("ssh-keygen -R %s" % _AppserverRepository.repository.hostname, quiet=True)
        run("ssh-keyscan -t rsa %s >> ~/.ssh/known_hosts" % _AppserverRepository.repository.hostname, quiet=True)
        print green("Updated ~/.ssh/known_hosts with \"%s\"." % _AppserverRepository.repository.hostname)

    # Remove appserver repo if it exists then clone the appserver repo 
    repository_path = "%s/%s" % (env.customer_path, _AppserverRepository.repository.destination_directory,)
    if exists(repository_path):
        run("rm -rf %s" % (repository_path,), quiet=True)
        print green("Existing repository \"%s\" removed." % repository_path)

    # Clone repository
    with cd(env.customer_path):
        run(_AppserverRepository.repository.clone_command_line, quiet=False)
    print green("Repository \"%s\" cloned." % repository_path)

    if _AppserverRepository.repository.version:
        with cd(repository_path):
            run(_AppserverRepository.repository.checkout_command_line, quiet=True)
            print green("Repository \"%s\" checked out at version '%s'." % (repository_path, _AppserverRepository.repository.version,))

    # Create buildout.cfg
    buildout_cfg_path = "%s/buildout.cfg" % (repository_path, )
    generate_buildout_cfg(buildout_cfg_path)

    print green("Repository \"%s\" cloned and buildout.cfg generated" % _AppserverRepository.repository.name)


@task
def openerp_bootstrap_appserver(adm_user=env.adm_user, adm_password=env.adm_password):
    """buildout bootstrap the application by launching install.sh"""
    env.user = adm_user
    env.password = adm_password
    appserver_path = '%s/%s/' % (env.customer_path, _AppserverRepository.repository.destination_directory, )
    with cd(appserver_path):
        run('./install.sh openerp')
    print green("Appserver installed.")


@task
def openerp_remove_appserver():
    """Remove init scripts and appserver repository"""
    env.user = env.root_user
    env.password = env.root_password

    # remove services
    openerp_remove_init_script_links()

    # remove appserver directory but leave 
    repository_path = "%s/%s" % (env.customer_path, _AppserverRepository.repository.destination_directory,)
    if exists(repository_path):
        run("rm -rf %s" % (repository_path,), quiet=True)
        print green("Existing repository \"%s\" removed." % repository_path)


@task
def openerp_create_services():
    """Create the openerp services (classic and gunicorn) and default to openerp classic"""
    env.user = env.root_user
    env.password = env.root_password

    appserver_path = '%s/%s/' % (env.customer_path, _AppserverRepository.repository.destination_directory, )

    replace_ctx = {
        'muppy_appserver_path': appserver_path,
        'muppy_adm_user': env.adm_user
    }
    muppy_utils.upload_template('scripts/openerp-server', '/etc/init.d/openerp-server', context=replace_ctx, use_sudo=True)
    muppy_utils.upload_template('scripts/gunicorn-openerp', '/etc/init.d/gunicorn-openerp', context=replace_ctx, use_sudo=True)

    sudo('chmod 755 /etc/init.d/openerp-server')
    sudo('chown %s:root /etc/init.d/openerp-server' % env.adm_user)

    sudo('chmod 755 /etc/init.d/gunicorn-openerp')
    sudo('chown %s:root /etc/init.d/gunicorn-openerp' % env.adm_user)

    sudo('update-rc.d openerp-server defaults')

    print green("OpenERP services created.")

@task
def openerp_remove_init_script_links(root_user=env.root_user, root_password=env.root_password):
    """Stop server, remove init.d script links, delete init.d scripts"""
    env.user = root_user
    env.password = root_password

    # Now stopping service
    print blue("Stopping openerp service...")
    sudo('/etc/init.d/openerp-server stop', quiet=True)
    sudo('/etc/init.d/gunicorn-openerp stop', quiet=True)

    print blue("Removing init script links...")
    sudo('update-rc.d -f gunicorn-openerp remove', quiet=True)
    sudo('update-rc.d -f openerp-server remove', quiet=True)

    print blue("Deleting /etc/init.d scripts file...")
    sudo('rm /etc/init.d/openerp-server', quiet=True)
    sudo('rm /etc/init.d/gunicorn-openerp', quiet=True)

    print green("OpenERP init scripts removed.")

@task
def install_openerp_application_server():
    """Install an OpenERP application server (without database)."""

    if not _AppserverRepository.enabled:
        print colors.red("ERROR: OpenERP configuration missing. Installation aborted.")
        sys.exit(1)
    
    system.prerequisites()

    if env.system.install:
        system.setup_locale()

    sys_install_openerp_prerequisites()
    
    sys_create_openerp_user()
    
    sys_create_customer_directory()
    sys_create_log_directory()
    sys_create_backup_directory()
    sys_create_muppy_transactions_directory()
    sys_create_buffer_directory()

    
    openerp_clone_appserver()
    openerp_bootstrap_appserver()
    
    openerp_create_services()
    
    reboot()

@task
def install_openerp_standalone_server(phase0='True', phase1='True', phase2='True', phase3='True', phase4='True', phase5='True', phase6='True'):
    """Install a complete OpenERP appserver (including database server). You must update/upgrade system before manually"""

    if not _AppserverRepository.enabled:
        print colors.red("ERROR: OpenERP configuration missing. Installation aborted.")
        sys.exit(1)

    phase0 = eval(phase0)
    phase1 = eval(phase1)
    phase2 = eval(phase2)
    phase3 = eval(phase3)
    phase4 = eval(phase4)
    phase5 = eval(phase5)
    phase6 = eval(phase6)

    system.prerequisites()

    # Install locale !
    if phase0:
        if env.system.install:
            system.setup_locale()

    # Install PostgreSQL
    if phase1:
        pg_install_server()
        pg_create_openerp_user()

    # Install System packages required for OpenERP
    if phase2:
        sys_install_openerp_prerequisites()

    # Create OpenERP admin user
    if phase3:
        sys_create_openerp_user()

    # Create directories (/opt/openerp/customer, /var/log)
    if phase4:
        sys_create_customer_directory()
        sys_create_log_directory()
        sys_create_backup_directory()
        sys_create_muppy_transactions_directory()
        sys_create_buffer_directory()

    if phase5:
        openerp_clone_appserver()
        openerp_bootstrap_appserver()
        
    # Setup init scripts
    if phase6:
        openerp_create_services()

    reboot()

@task
def openerp_archive_appserver(root_user=env.root_user, root_password=env.root_password):
    """Archive the appserver directory into a directory named appserver.archived_YYYY-MM-DD"""
    env.user = root_user
    env.password = root_password
    repository_path = "%s/%s" % (env.customer_path, _AppserverRepository.repository.destination_directory,)

    sudo('rm -rf %s.achived_%s' % (repository_path, datetime.date.today()))
    sudo('mv %s %s.achived_%s' % (repository_path, repository_path, datetime.date.today(),))

@task
def openerp_reinstall_appserver():
    """Re-install OpenERP appserver"""

    if not _AppserverRepository.enabled:
        print colors.red("ERROR: OpenERP configuration missing. Installation aborted.")
        sys.exit(1)

    sys_create_openerp_user()

    sys_create_customer_directory()
    sys_create_log_directory()
    sys_create_backup_directory()
    sys_create_muppy_transactions_directory()
    sys_create_buffer_directory()
    
    openerp_remove_init_script_links()
    openerp_archive_appserver()
    
    openerp_clone_appserver()
    openerp_bootstrap_appserver()
    
    openerp_create_services()
    
    reboot()


@task
def ssh(user='adm'):
    """:adm | root | lxc -  Launch an SSH session into host with corresponding user. adm_user (default) or root_user ..."""
    env.user = env.adm_user
    env.password = env.adm_password

    if user == 'adm':
        ssh_user = env.adm_user
        ssh_password = env.adm_password
    elif user == 'root':
        ssh_user = env.root_user
        ssh_password = env.root_password
    elif user == 'lxc':
        ssh_user = env.lxc.user_name
        ssh_password = env.lxc.user_password
    else:
        print colors.red("ERROR: Unknown user %s !" % user)
        sys.exit(1)

    print "Password= "+ blue("%s" % ssh_password)
    
    subprocess.call(["ssh", "-p %s" % (env.port,), "%s@%s" % (ssh_user, env.host)])

