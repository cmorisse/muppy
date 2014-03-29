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

import muppy_utils

from muppy_magento import *
import vagrant
import postgresql
import openerp
import security

import pudb

__version__ = '0.2.6'

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


if config_parser.has_option('env', 'hosts'):
    env.hosts = config_parser.get('env', 'hosts').split(',')
env.root_user = config_parser.get('env', 'root_user')
env.root_password = config_parser.get('env', 'root_password')


env.adm_user = (config_parser.has_option('env', 'adm_user') and config_parser.get('env', 'adm_user')) or env.root_user
env.adm_password = (config_parser.has_option('env', 'adm_password') and config_parser.get('env', 'adm_password')) or env.root_password
env.adm_user_is_sudoer = (config_parser.has_option('env', 'adm_user_is_sudoer') and config_parser.get('env', 'adm_user_is_sudoer')) or False


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


# TODO: eval root, adm, pg, postgres, user and password from os.environ

class _AppserverRepository:
    pass


class Repository(object):
    def __init__(self, user, password, url, base_path):
        self.dvcs, self.clone_url, self.destination_directory, self.version, self.name, \
        self.owner, self.protocol = Repository.parse_appserver_url(url)

        self.user = user
        self.password = password

        self.base_path = base_path

    @staticmethod
    def parse_appserver_url(url):
        """
        Accept a appserver_url of the form: {dvcs} {clone_url} [destination_directory] [version]
        :returns a list of 7 elements:
        [
            dvcs,
            clone_url,
            destination_directory,
            version,
            repository_name,
            owner_name,
            protocol
        ]
        """
        ret_list = [None] * 7  # Create a list of 7 None elements
    
        url_components = url.split(' ')
        ret_list[0:len(url_components)] = url_components  # Feed what we can
    
        if ret_list[0] not in ('git', 'hg'):
            print red("Error: unsupported dvcs : %s. Must be 'hg' or 'git'." % ret_list[0])
    
        # we extrace repository name from url
        if ret_list[0] == 'git':
            if ret_list[1].startswith('git'):
                owner_name = ret_list[1].split(':')[1].split('/')[0]
                repository_name = ret_list[1].split(':')[1].split('/')[-1][:-4]
            else:
                # https
                owner_name = ret_list[1].split('/')[-2]
                repository_name = ret_list[1].split('/')[-1][:-4]
        else:
            # mercurial
            owner_name = ret_list[1].split('/')[-2]
            repository_name = ret_list[1].split('/')[-1]
    
        ret_list[4] = repository_name
        ret_list[5] = owner_name
    
        # protocol
        protocol_prefix = ret_list[1][:3]
        ret_list[6] = 'ssh' if protocol_prefix in ('git', 'ssh',) else 'https'

        # let destination_directory to repository_name if undefined
        ret_list[2] = ret_list[2] or ret_list[4]

        return ret_list

    @property
    def hostname(self):
        if self.clone_url.startswith('git'):
            return self.clone_url.split(':')[0].split('@')[1]
        elif self.clone_url.startswith('http'):
            subs = self.clone_url.split('//')[1].split('/')[0]
            if subs.find('@') > 0:
                return subs.split('@')[1]
            return subs
        elif self.clone_url.startswith('ssh'):
            return self.clone_url.split('//')[1].split('/')[0].split('@')[1]
        return ''

    @property
    def path(self):
        return os.path.join(self.base_path, self.destination_directory)

    def get_refspec_command_line(self):
        """Returns shell command to retrieve current active revision in repository"""
        if self.dvcs == 'git':
            return 'git rev-parse --verify HEAD'
        elif self.dvcs == 'hg':
            # mercurial
            return 'hg id -i'

    def get_show_current_rev_command_line(self):
        """Returns shell command to display info about current revision in repository"""
        if self.dvcs == 'git':
            return 'git show --format=medium -s HEAD'
        elif self.dvcs == 'hg':
            return 'hg sum'

    def get_fetch_command_line(self, source=''):
        """Returns a git fetch or hg pull command line"""
        if self.dvcs == 'git':
            return 'git fetch origin %s' % source
        elif self.dvcs == 'hg':  # mercurial
            return 'hg pull %s' % source
    
    def get_checkout_command_line(self, refspec):
        """Returns a git checkout or hg update command line"""
        if self.dvcs == 'git':
            return 'git checkout %s' % refspec
        elif self.dvcs == 'hg':  # mercurial
            return 'hg update %s' % refspec


class BitbucketRepository(Repository):

    def __init__(self, user, password, url, base_path):
        super(BitbucketRepository, self).__init__(user, password, url, base_path)

    def search_deployment_key(self, key_name=''):
        if not key_name:
            return []
        url = "https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (self.owner, self.name)
        response = requests.get(url, auth=(self.user, self.password))
        if response.status_code != requests.codes.ok:
            return []

        key_list = response.json()
        result = [key['pk'] for key in key_list if str(key['label']) == key_name]
        return result

    def post_deployment_key(self, key_name, key_string):
        """
        Upload a deployment key to repo
        :param key_name: Name of the key to upload (bitbucket's label).
        :type key_name: str
        :param key_string: SSH Key
        :type key_string: str
        :return: True or False
        :rtype: boolean
        """
        url = "https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (self.owner, self.name,)
        auth = (self.user, self.password,)
        data = {
            'label': key_name,
            'key': key_string
        }
        res = requests.post(url, auth=auth, data=data)
        if res.status_code != requests.codes.ok:
            print red("Error: Unable to upload deployment key to bitbucket.")
            return False
        return True

    def delete_deployment_key(self, pk):
        """
        Delete deployment key
        :param pk: a bitbucket pk
        :type pk: str or int
        :return: True or False
        :rtype: boolean
        """
        url = "https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/%s" % (self.owner, self.name, pk)
        auth = (self.user, self.password,)
        response = requests.delete(url, auth=auth)
        if response.status_code != 204:  # Bitbucket : WTF 204 ?? !!!!
            return False
        return True

    def update_deployment_key(self, key_name, key_string):
        """
        Delete existing deployment keys named as key_name, then upload a new one
        :param key_name: Name of the key to update (bitbucket's label).
        :type key_name: str
        :param key_string: SSH Key
        :type key_string: str
        :return: True or False
        :rtype: boolean
        """
        # for update, we don't bother if key do not exists
        keys = self.search_deployment_key(key_name)
        for key in keys:
            self.delete_deployment_key(key)
        return self.post_deployment_key(key_name, key_string)

    @property
    def clone_command_line(self):
        if self.dvcs == 'hg':
            if self.version:
                return "hg clone -y -r %s %s %s" % (self.version, self.clone_url, self.destination_directory,)
            return "hg clone -y %s %s" % (self.clone_url, self.destination_directory,)

        # elif self.dvcs == 'git':
        return "git clone %s %s" % (self.clone_url, self.destination_directory,)

    @property
    def checkout_command_line(self):
        if not self.version:
            return ''
        if self.dvcs == 'hg':
            return "hg update %s" % (self.version,)
        # elif self.dvcs == 'git':
        return "git checkout %s" % (self.version,)

    @property
    def pull_command_line(self):
        if self.dvcs == 'hg':
            return "hg pull -u'"
        # elif self.dvcs == 'git':
        return "git pull origin master"


if config_parser.has_section('appserver_repository'):
    _AppserverRepository.server_type = config_parser.get('appserver_repository', 'server_type')
    if _AppserverRepository.server_type not in ('gitlab', 'bitbucket'):
        print red("Error: Unsupported value for appserver_repository.server_type : %s" % _AppserverRepository.server_type)
        exit(-1)
    _AppserverRepository.appserver_url = (config_parser.has_option('appserver_repository', 'appserver_url') and config_parser.get('appserver_repository', 'appserver_url')) or "git git@bitbucket.org:cmorisse/appserver-templatev7.git"
    _AppserverRepository.other_private_repo_urls = (config_parser.has_option('appserver_repository', 'other_private_repo_urls') and config_parser.get('appserver_repository', 'other_private_repo_urls')) or ''

    str_to_eval = config_parser.get('appserver_repository', 'user')
    _AppserverRepository.user = eval(str_to_eval, {'os': os})

    str_to_eval = config_parser.get('appserver_repository', 'password')
    _AppserverRepository.password = eval(str_to_eval, {'os': os})

    if _AppserverRepository.server_type == 'bitbucket':
        _AppserverRepository.repository = BitbucketRepository(_AppserverRepository.user,
                                                              _AppserverRepository.password,
                                                              _AppserverRepository.appserver_url,
                                                              env.customer_path)
    env.openerp = _AppserverRepository
else:
    print red("Error: [appserver_repository] section missing in config file")
    exit(-1)


@task
def mupping(root_user=env.root_user, root_password=env.root_password):
    """Mup"ping": try to run ls then sudo ls over ssh"""
    env.user = root_user
    env.password = root_password
    run("ls /") 
    sudo("ls /")   
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
# VMware Tools Installation (shitty)
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
def sys_update_upgrade():
    """Update and upgrade system (with apt-get)"""
    env.user = env.root_user
    env.password = env.root_password
    
    sudo("apt-get update --fix-missing")
    sudo("apt-get upgrade -y")
    print green("System updated and upgraded")

@task
def sys_install_openerp_prerequisites():
    """Install all ubuntu packages required for OpenERP Server (run as root_user)"""
    env.user = env.root_user
    env.password = env.root_password

    # TODO All of this must move to the repository install.sh
    sudo('wget https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py')
    sudo('python ez_setup.py')
    sudo('rm ez_setup.py')

    sudo("easy_install virtualenv==1.11.4")

    sudo("apt-get install -y python-dev libz-dev")
    sudo("apt-get install -y bzr mercurial git")
    sudo("apt-get install -y libxml2-dev libxslt1-dev")
    sudo("apt-get install -y libpq-dev")
    sudo("apt-get install -y libldap2-dev libsasl2-dev")
    sudo("apt-get install -y libjpeg-dev libfreetype6-dev liblcms2-dev liblcms1-dev libwebp-dev libtiff-dev")
    sudo("apt-get install -y libyaml-dev")

    sudo("apt-get install -y curl htop vim")

    print green("OpenERP prerequisites installed.")

@task
def user_get_groups(user_name):
    env.user = env.root_user
    env.password = env.root_password
    groups = sudo('groups %s' % user_name, warn_only=True)
    if groups.failed:
        return []
    return groups.split(':')[1].lstrip().split(' ')


@task
def user_set_password(user_name, user_password):
    env.user = env.root_user
    env.password = env.root_password
    # set password for adm_user
    sudo("echo '%s:%s' > pw.tmp" % (user_name, user_password,), quiet=True)
    sudo("sudo chpasswd < pw.tmp", quiet=True)
    sudo("rm pw.tmp", quiet=True)
    print green("User \"%s\" password set." % user_name)


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
def user_exists(user_name):
    env.user = env.root_user
    env.password = env.root_password
    return user_search(user_name) != ''

@task
def get_hostname():
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    hostname = run("hostname", warn_only=True, quiet=True)

    (env.user, env.password,) = env_backup 
    return hostname

def get_sshkey_name():
    return 'muppy:%s@%s' % (env.adm_user, get_hostname(),)

def update_ssh_key_on_private_repositories(sshkey_string):
    """
    Update ssh-key on all private repositories
    """
    if _AppserverRepository.server_type == 'gitlab':
        pass
    elif _AppserverRepository.server_type == 'bitbucket':
        # first we update key on appserver repository
        repo = BitbucketRepository(_AppserverRepository.user,
                                   _AppserverRepository.password,
                                   _AppserverRepository.appserver_url,
                                   env.customer_path)
        if repo.update_deployment_key(get_sshkey_name(), sshkey_string):
            print green("Deployment key (%s) successfully added to bitbucket repository \"%s\"." % (get_sshkey_name(), repo.name))
        else:
            print red("Error: Unable to update deployment key for bitbucket repository :%s/%s" % (repo.owner, repo.name))

        # then we update keys on others repositories
        repo_url_list = [] or (_AppserverRepository.other_private_repo_urls and _AppserverRepository.other_private_repo_urls.split('\n'))
        for repo_url in repo_url_list:
            repo = BitbucketRepository(_AppserverRepository.user,
                                       _AppserverRepository.password,
                                       repo_url,
                                       env.customer_path)
            if repo.update_deployment_key(get_sshkey_name(), sshkey_string):
                print green("Deployment key (%s) successfully uploaded to bitbucket repository %s/%s." % (get_sshkey_name(), repo.owner, repo.name,))
            else:
                print red("Error: Unable to update deployment key (%s) for bitbucket repository :%s/%s" % (get_sshkey_name(), repo.owner, repo.name))


@task
def sys_create_openerp_user(root_user=env.root_user, root_password=env.root_password):
    """Create openerp admin user"""
    env.user = root_user
    env.password = root_password

    # create adm_user if it does not exists
    if not user_search(env.adm_user):
        sudo("useradd -m -s /bin/bash --system %s" % (env.adm_user,))

    # manage adm_user sudo membership
    if env.adm_user_is_sudoer:
        if not 'sudo' in user_get_groups(env.adm_user):
            sudo('usermod -a -G sudo %s' % env.adm_user)
    else:
        if 'sudo' in user_get_groups('env.adm_user'):
            sudo('deluser %s sudo' % env.adm_user)

    user_set_password(env.adm_user, env.adm_password)

    # Generate a ssh key for adm_user if it does not exists
    env.user = env.adm_user
    env.password = env.adm_password
    if not exists('~/.ssh/id_rsa'):
        run("ssh-keygen -t rsa -N \"\" -f ~/.ssh/id_rsa")

    # download ssh key
    host_name = get_hostname()
    ssh_key_file_name = 'ssh_keys_temp/%s__%s__id_rsa.pub' % (host_name, env.adm_user,)
    get('/home/%s/.ssh/id_rsa.pub' % (env.adm_user,), ssh_key_file_name)
    ssh_key_file = open(ssh_key_file_name)
    ssh_key_string = ssh_key_file.read()

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

    buildout_content = """[buildout]
extends = %s
[openerp]
options.admin_passwd = %s
options.db_user = %s
options.db_password = %s
""" % (base_template_name, env.openerp_admin_password, env.db_user, env.db_password,)

    put(StringIO.StringIO(buildout_content), buildout_cfg_path)
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

    # Create buildout.cfg by copying template
    buildout_cfg_path = "%s/buildout.cfg" % (repository_path, )
#    run("cp %s.template %s" % (buildout_cfg_path, buildout_cfg_path,), quiet=True)

    # Adjust buildout.cfg content
 #   sed(buildout_cfg_path, "\{\{pg_user\}\}", sed_escape(env.db_user))
 #   sed(buildout_cfg_path, "\{\{pg_password\}\}", sed_escape(env.db_password))
 #   sed(buildout_cfg_path, "\{\{openerp_admin_password\}\}", sed_escape(env.openerp_admin_password))
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
def openerp_create_services(root_user=env.root_user, root_password=env.root_password):
    """Create the openerp services (classic and gunicorn) and default to openerp classic"""
    env.user = root_user
    env.password = root_password

    appserver_path = '%s/%s/' % (env.customer_path, _AppserverRepository.repository.destination_directory, )

    replace_ctx = {
        'muppy_appserver_path': appserver_path,
        'muppy_adm_user': env.adm_user
    }
    upload_template('scripts/openerp-server', '/etc/init.d/openerp-server', context=replace_ctx, use_sudo=True, backup=True, use_jinja=True)
    upload_template('scripts/gunicorn-openerp', '/etc/init.d/gunicorn-openerp', context=replace_ctx, use_sudo=True, backup=True, use_jinja=True)

    sudo('chmod 755 /etc/init.d/openerp-server')
    sudo('chown %s:root /etc/init.d/openerp-server' % env.adm_user)

    sudo('chmod 755 /etc/init.d/gunicorn-openerp')
    sudo('chown %s:root /etc/init.d/gunicorn-openerp' % env.adm_user)

    sudo('update-rc.d openerp-server defaults')

    print green("OpenERP services created.")

@task
def openerp_remove_init_script_links(root_user=env.root_user, root_password=env.root_password):
    """Stop server, remove init-script links, delete system scripts"""
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
def install_openerp_standalone_server(phase_1='True', phase_2='True', phase_3='True', phase_4='True', phase_5='True', phase_6='True'):
    """Install a complete OpenERP appserver (including database server). You must update/upgrade system before manually"""
    
    phase_1 = eval(phase_1)
    phase_2 = eval(phase_2)
    phase_3 = eval(phase_3)
    phase_4 = eval(phase_4)
    phase_5 = eval(phase_5)
    phase_6 = eval(phase_6)
    
    # Install PostgreSQL
    if phase_1:
        pg_install_server()
        pg_create_openerp_user()

    # Install System packages required for OpenERP
    if phase_2:
        sys_install_openerp_prerequisites()

    # Create OpenERP admin user
    if phase_3:
        sys_create_openerp_user()

    # Create directories (/opt/openerp/customer, /var/log)
    if phase_4:
        sys_create_customer_directory()
        sys_create_log_directory()
        sys_create_backup_directory()
        sys_create_muppy_transactions_directory()
        sys_create_buffer_directory()


    if phase_5:
        openerp_clone_appserver()
        openerp_bootstrap_appserver()
        
    # Setup init scripts
    if phase_6:
        openerp_create_services()

    reboot()

@task
def openerp_archive_appserver(root_user=env.root_user, root_password=env.root_password):
    """Archive the appserver directory into a directory named appserver.archived_YYYY-MM-DD"""
    env.user = root_user
    env.password = root_password
    repository_path = "%s/%s" % (env.customer_path, _AppserverRepository.repository.desdestination_directory,)

    sudo('rm -rf %s.achived_%s' % (repository_path, datetime.date.today()))
    sudo('mv %s %s.achived_%s' % (repository_path, repository_path, datetime.date.today(),))

@task
def openerp_reinstall_appserver():
    """Re-install OpenERP appserver"""
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
def ssh(user='adm_user'):
    """:[[root]] Launch an SSH session into host using either adm_user (default) or root_user if [[root]] parameter is supplied"""
    env.user = env.adm_user
    env.password = env.adm_password

    if user != 'adm_user':
        ssh_user = env.root_user
        ssh_password = env.root_password
    else:
        ssh_user = env.adm_user
        ssh_password = env.adm_password
    
    print "Password= "+ blue("%s" % ssh_password)
    
    ssh = subprocess.call(["ssh", "-p %s" % (env.port,), "%s@%s" % (ssh_user, env.host)])

