# coding: utf8
from fabric.api import *
from fabric.contrib.files import upload_template, exists, sed
from fabric.colors import *
import ConfigParser
import requests
from datetime import date

__version__ = '0.1 beta'

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
if config_parser.has_option('env', 'hosts'):
    env.hosts = config_parser.get('env', 'hosts').split(',')
env.root_user = config_parser.get('env', 'root_user')
env.root_password = config_parser.get('env', 'root_password')
env.adm_user = config_parser.get('env', 'adm_user')
env.adm_password = config_parser.get('env', 'adm_password')
env.adm_user_is_sudoer = config_parser.get('env', 'adm_user_is_sudoer')
env.pg_user = config_parser.get('env', 'pg_user')
env.pg_password = config_parser.get('env', 'pg_password')
env.system_suffix = config_parser.get('env', 'system_suffix')
env.customer_directory = config_parser.get('env', 'customer_directory')
env.openerp_admin_password = config_parser.get('env', 'openerp_admin_password')
env.addons_list = config_parser.get('env', 'addons_list')

# TODO: expand bash vars for password

class _bitbucket:
    pass

if config_parser.has_section('bitbucket'):
    if config_parser.has_option('bitbucket', 'repository_type'):
        _bitbucket.repository_type = config_parser.get('bitbucket', 'repository_type')
    else:
        _bitbucket.repository_type = 'hg'

    _bitbucket.protocol = config_parser.get('bitbucket', 'protocol') 
    _bitbucket.user = config_parser.get('bitbucket', 'user')
    _bitbucket.password = config_parser.get('bitbucket', 'password')

    _bitbucket.appserver_user = config_parser.get('bitbucket', 'appserver_user')    
    _bitbucket.appserver_repository = config_parser.get('bitbucket', 'appserver_repository')
    _bitbucket.appserver_destination_directory = config_parser.get('bitbucket', 'appserver_destination_directory')

    _bitbucket.other_private_repositories = config_parser.get('bitbucket', 'other_private_repositories').split(',')
else:
    print red("Error: [bitbucket] configuration missing in config file")
    exit(-1)


def mupping(root_user=env.root_user, root_password=env.root_password):
    """Mup.py "ping": try to run ls then sudo ls over ssh"""
    env.user = root_user
    env.password = root_password
    run("ls /") 
    sudo("ls /")   
    return


#
# PostgreSQL Installation related functions
#
def pg_install_server(root_user=env.root_user, root_password=env.root_password):
    """Install Postgresql Server and CLI Client."""
    env.user = root_user
    env.password = root_password
    
    sudo('apt-get update --fix-missing')
    sudo('apt-get install -y vim gcc python-setuptools postgresql graphviz postgresql-client libyaml-0-2')
    print green("PosgreSQL server and client installed.")

def pg_create_openerp_user(pg_user=env.pg_user, pg_password=env.pg_password):
    """Create a Postgres User for OpenERP Server"""
    env.user = env.root_user
    env.password = env.root_password

    sudo( """su postgres -c 'echo "CREATE ROLE %s WITH LOGIN SUPERUSER CREATEDB NOCREATEROLE ENCRYPTED PASSWORD '"'"'%s'"'"' ;" | psql ' """ % (pg_user, pg_password) )
    print green("PosgreSQL %s user created." % pg_user)

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

def pg_install_db_server(pg_user=env.pg_user, pg_password=env.pg_password):
    """Install PostgreSQL server then create database user"""
    pg_install_server()
    pg_create_openerp_user(pg_user=pg_user, pg_password=pg_password)

#
# VMware Tools Installation (shitty)
#
def sys_install_vmware_tools(root_user=env.root_user, root_password=env.root_password):
    """VMWare Tools Installation (requires the tools ISO to be mounted)"""
    env.user = root_user
    env.password = root_password

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
def sys_update_upgrade():
    """Update and upgrade system (with apt-get)"""
    env.user = env.root_user
    env.password = env.root_password
    
    sudo("apt-get update")
    sudo("apt-get upgrade -y")
    print green("System updated and upgraded")

def sys_install_openerp_prerequisites(root_user=env.root_user, root_password=env.root_password):
    """Install all ubuntu packages required for OpenERP Server (run as root_user)"""
    env.user = root_user
    env.password = root_password

    sudo("apt-get install -y python-dev")
    sudo("apt-get install -y libldap2-dev libxslt1-dev libsasl2-dev libjpeg62 libjpeg62-dev libfreetype6-dev liblcms2-dev liblcms1-dev")
    sudo("apt-get install -y postgresql-client libpq-dev python-psycopg2")
    sudo("apt-get install -y python-markupsafe python-imaging python-libxml2 python-dateutil python-feedparser python-gdata python-ldap python-libxslt1 python-lxml python-mako python-openid python-pybabel python-pychart python-pydot python-pyparsing python-reportlab python-simplejson python-vatnumber python-vobject python-tz python-webdav python-werkzeug python-yaml python-xlwt python-zsi")
    sudo("apt-get install -y bzr python-bzrlib mercurial git python-virtualenv python-pip vim curl")
    sudo("apt-get install -y htop")
    print green("OpenERP prerequisites installed.")

def sys_create_openerp_user(root_user=env.root_user, root_password=env.root_password):
    """Create openerp admin user"""
    env.user = root_user
    env.password = root_password

    # Create the user ; he can be sudoer or not depending on the adm_user_is_sudoer config 
    if True:
        if env.adm_user_is_sudoer:
            sudo("useradd -m -s /bin/bash --system --group sudo %s" % (env.adm_user,))
            #sudo("useradd -m -s /bin/bash --system --group openerp %s" % (env.adm_user,))
        else:
            sudo("useradd -m -s /bin/bash --system %s" % (env.adm_user,))
    
        sudo("echo \"%s:%s\" > pw.tmp" % (env.adm_user, env.adm_password,))
        sudo("sudo chpasswd < pw.tmp")
        sudo("rm pw.tmp")
        print green("User \"%s\" created." % env.adm_user)

    if True:
        # Generate a ssh key and package it 
        env.user = env.adm_user
        env.password = env.adm_password
        run("ssh-keygen -t rsa -N \"\" -f ~/.ssh/id_rsa")

    if True:
        # TODO: use a ./tmp directory to store working files
        env.user = env.adm_user
        env.password = env.adm_password
        get('/home/%s/.ssh/id_rsa.pub' % (env.adm_user,), 'ssh_keys_temp/%s_id_rsa.pub' % (env.adm_user,))

        ssh_key_file = open('ssh_keys_temp/%s_id_rsa.pub' % (env.adm_user,))
        data = {
            'label': 'muppy:%s@%s' % (env.adm_user, env.host,),
            'key': ssh_key_file.read()
        }

    if True:
        # Upload the key to bitbucket.org as a deployment (readonly) key on the app-server repository
        # TODO: test if key exists before generating a new one or delete existing keys
        res = requests.post("https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (_bitbucket.appserver_user, _bitbucket.appserver_repository,),
                            auth=(_bitbucket.user, _bitbucket.password),
                            data=data)
        
        assert res.status_code == requests.codes.ok, "Error: Unable to upload deployment key to bitbucket.org"
        print green("Deployment key (%s) successfully generated and uploaded to bitbucket." % data['label'])

    if True:
        # Upload the key to all others private repos
        # TODO: Infer this list from the buildout.cfg addons key 
        for repo in _bitbucket.other_private_repositories:
            if repo:
                user, repository = repo.split('/')
                if user and repository:
                    res = requests.post("https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (user, repository,),
                                        auth=(_bitbucket.user, _bitbucket.password),
                                        data=data)
                    assert res.status_code == requests.codes.ok, "Error: Unable to upload deployment key to bitbucket.org"
                    print green("Deployment key (%s) successfully uploaded to repository :%s" % (data['label'], repository))
                else:
                    print red("%s is not a valid repository name!" % repo)

def sys_update_deployment_key(root_user=env.root_user, root_password=env.root_password):
    """Retrieve user ssh key and upload it as a deployment key on all repositories (main and other privates)."""
    env.user = root_user
    env.password = root_password

    # TODO: use a ./tmp directory to store working files
    env.user = env.adm_user
    env.password = env.adm_password
    ssh_key_temp_file_name = '%s_%s_id_rsa.pub' % (_bitbucket.appserver_repository, env.adm_user,)
    get('/home/%s/.ssh/id_rsa.pub' % (env.adm_user,), 'ssh_keys_temp/%s' % (ssh_key_temp_file_name,))

    ssh_key_file = open('ssh_keys_temp/%s' % (ssh_key_temp_file_name,))
    data = {
        'label': 'muppy:%s@%s' % (env.adm_user, env.host,),
        'key': ssh_key_file.read()
    }

    # Upload the key to bitbucket.org as a deployment (readonly) key on the app-server repository
    # TODO: test if key exists before generating a new one or delete existing keys
    res = requests.post("https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (_bitbucket.appserver_user, _bitbucket.appserver_repository,),
                        auth=(_bitbucket.user, _bitbucket.password),
                        data=data)
    
    assert res.status_code == requests.codes.ok, "Error: Unable to upload deployment key to bitbucket.org"
    print green("Deployment key (%s) successfully generated and uploaded to bitbucket." % data['label'])

    # Upload the key to all others private repos
    # TODO: Infer this list from the buildout.cfg addons key 
    for repo in _bitbucket.other_private_repositories:
        if repo:
            user, repository = repo.split('/')
            if user and repository:
                res = requests.post("https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (user, repository,),
                                    auth=(_bitbucket.user, _bitbucket.password),
                                    data=data)
                assert res.status_code == requests.codes.ok, "Error: Unable to upload deployment key to bitbucket.org"
                print green("Deployment key (%s) successfully uploaded to repository :%s" % (data['label'], repository))
            else:
                print red("%s is not a valid repository name!" % repo)

def sys_create_customer_directory(root_user=env.root_user, root_password=env.root_password):
    """Create Customer directory (/opt/openerp/<customer>) owned by adm_user""" 
    # Create :
    #   - Customer directory (/opt/openerp/<customer>) that will hold all subprojects related to this server.
    #  Grant rights only to adm_user (run as root_user)
    env.user = root_user
    env.password = root_password

    customer_path = "/opt/openerp/%s" % (env.customer_directory,)
    sudo("mkdir -p %s" % (customer_path,))
    sudo("chmod 755 %s" % (customer_path,))     
    sudo("chown -R %s: %s" % (env.adm_user, customer_path,))
    print green("Directory %s created." % customer_path )

def sys_create_log_directory(root_user=env.root_user, root_password=env.root_password):
    """Create openerp server log directory ( /var/log/openerp ) and grant rights to adm_user""" 
    # Create :
    #   - Openerp log directory
    #  Grant rights only to adm_user (run as root_user)
    env.user = root_user
    env.password = root_password

    print blue("Creating openerp log directory (/var/log/openerp) and grant adm_user rights to it")
    sudo('mkdir -p /var/log/openerp')
    sudo('chown -R %s:root /var/log/openerp' % (env.adm_user,))
    sudo('chmod 775 /var/log/openerp')
    print green("OpenERP log directory: \"/var/log/openerp/\" created.")

#
# OpenERP related tasks
#
def openerp_clone_appserver(adm_user=env.adm_user, adm_password=env.adm_password):
    """Clone an appserver repository and setup buildout.cfg"""
    # appserver must hast been created after http://bitbucket.org/cmorisse/template-appserver-v7

    def sed_escape(s):
        """Utility to preserve special characters in password during sed(ing) of buildout.cfg"""
        t1 = s.replace("\\", "\\\\")
        t2 = t1.replace("/", "\\/")
        t3 = t2.replace("&", "\&")
        return t3

    env.user = adm_user
    env.password = adm_password

    # Add bitbucket SSH key in known_hosts on remote server
    if _bitbucket.protocol=='ssh':
        if exists("~/.ssh/known_hosts"):
            run("ssh-keygen -R bitbucket.org")  # Remove host from known_hosts file
        run("ssh-keyscan -t rsa bitbucket.org >> ~/.ssh/known_hosts")  # Add bitbucket.org in known host

    # Remove appserver repo if it exists then clone the appserver repo 
    customer_path = "/opt/openerp/%s" % (env.customer_directory,)
    repository_path = "%s/%s" % (customer_path, _bitbucket.appserver_destination_directory or _bitbucket.appserver_repository,) 
    if exists(repository_path):
        run("rm -rf %s" % (repository_path,))

    if _bitbucket.repository_type == 'hg':
        if _bitbucket.protocol == 'ssh':
            run("hg clone -y ssh://hg@bitbucket.org/%s/%s %s" % (_bitbucket.appserver_user, _bitbucket.appserver_repository, repository_path,))
        else:
            run("hg clone -y https://%s:%s@bitbucket.org/%s/%s %s" % (_bitbucket.user, _bitbucket.password, _bitbucket.appserver_user, _bitbucket.appserver_repository, repository_path,))
    else:
        # So Let's git it
        if _bitbucket.protocol == 'ssh':
            run("git clone git@bitbucket.org:%s/%s %s" % (_bitbucket.appserver_user, _bitbucket.appserver_repository, repository_path,))
        else:
            run("git clone https://%s:%s@bitbucket.org/%s/%s %s" % (_bitbucket.user, _bitbucket.password, _bitbucket.appserver_user, _bitbucket.appserver_repository, repository_path,))

    # Create buildout.cfg by copying template
    buildout_cfg_path = "%s/buildout.cfg" % (repository_path, )
    run("cp %s.template %s" % (buildout_cfg_path, buildout_cfg_path,))
    # Adjust buildout.cfg content
    sed(buildout_cfg_path, "\{\{pg_user\}\}", sed_escape(env.pg_user))
    sed(buildout_cfg_path, "\{\{pg_password\}\}", sed_escape(env.pg_password))
    sed(buildout_cfg_path, "\{\{openerp_admin_password\}\}", sed_escape(env.openerp_admin_password))

    print green("Bitbucket repository \"%s\" cloned" % _bitbucket.appserver_repository)

def openerp_bootstrap_appserver(adm_user=env.adm_user, adm_password=env.adm_password):
    """buildout bootstrap the application launching install.sh"""
    env.user = adm_user
    env.password = adm_password

    customer_path = "/opt/openerp/%s" % (env.customer_directory,)
    appserver_path = '%s/%s/' % (customer_path, _bitbucket.appserver_destination_directory or _bitbucket.appserver_repository, )

    with cd(appserver_path):
        run('./install.sh openerp')
    print green("Appserver installed.")


def openerp_create_services(root_user=env.root_user, root_password=env.root_password):
    """Create the openerp services (classic and gunicorn) and default to openerp classic"""
    env.user = root_user
    env.password = root_password

    customer_path = "/opt/openerp/%s" % (env.customer_directory,)
    appserver_path = '%s/%s/' % (customer_path, _bitbucket.appserver_destination_directory or _bitbucket.appserver_repository, )

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



def openerp_remove_init_script_links(root_user=env.root_user, root_password=env.root_password):
    """Stop server, remove init-script links, delete system scripts"""
    env.user = root_user
    env.password = root_password

    # Now stopping service
    print blue("Stopping openerp service...")
    sudo('/etc/init.d/openerp-server stop')
    sudo('/etc/init.d/gunicorn-openerp stop')

    print blue("Removing init script links...")
    sudo('update-rc.d -f gunicorn-openerp remove')
    sudo('update-rc.d -f openerp-server remove')

    print blue("Deleting init.d scipts file...")
    sudo('rm /etc/init.d/openerp-server')
    sudo('rm /etc/init.d/gunicorn-openerp')

    print green("OpenERP init scipts removed.")

def install_openerp_application_server():
    """Install an OpenERP application server (without database)."""
    sys_install_openerp_prerequisites()
    sys_create_openerp_user()
    sys_create_directories()

    openerp_clone_appserver()
    openerp_bootstrap_appserver()
    openerp_create_services()
    reboot()


def install_openerp_standalone_server(phase_1=True, phase_2=True, phase_3=True, phase_4=True, phase_5=True, phase_6=True):
    """Install a complete OpenERP appserver (including database server). You must update/upgrade system before manually"""
    
    #phase_1 = phase_2 = phase_3 = phase_4 = phase_5 = phase_6 = False
        
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

    if phase_5:
        openerp_clone_appserver()
        openerp_bootstrap_appserver()
        
    # Setup init scripts
    if phase_6:
        openerp_create_services()

    reboot()

def openerp_archive_appserver(root_user=env.root_user, root_password=env.root_password):
    """Move achive the appserver directory into a directory named appserver.archived_YYYY-MM-DD"""
    env.user = root_user
    env.password = root_password
    customer_path = "/opt/openerp/%s" % (env.customer_directory,)
    repository_path = "%s/%s" % (customer_path, _bitbucket.appserver_destination_directory or _bitbucket.appserver_repository,) 

    sudo('rm -rf %s.achived_%s' % (repository_path, date.today()))
    sudo('mv %s %s.achived_%s' % (repository_path, repository_path, date.today(),))


def openerp_reinstall_appserver(phase_1=True, phase_2=True, phase_3=True, phase_4=True, phase_5=True, phase_6=True):
    """Re-install OpenERP appserver"""

    #TODO: check pre requisites: deployement key uploaded
    openerp_remove_init_script_links()
    openerp_archive_appserver()
    openerp_clone_appserver()
    openerp_bootstrap_appserver()
    openerp_create_services()
    reboot()

def stop_openerp_service():
    """Stop openerp service"""
    # We switch to root_user, but we preserve active usert
    backup_user = env.user
    backup_password = env.password

    env.user = env.root_user
    env.password = env.root_password        
    sudo('/etc/init.d/openerp-server stop', pty=False)

    env.user = backup_user
    env.password = backup_password 
    print green("openerp-server stopped")

def start_openerp_service():
    """Start openerp service"""
    # We switch to root_user, but we preserve active usert
    backup_user = env.user
    backup_password = env.password

    env.user = env.root_user
    env.password = env.root_password        
    sudo('/etc/init.d/openerp-server start', pty=False)

    env.user = backup_user
    env.password = backup_password 
    print green("openerp-server started")

def update_appserver(adm_user=env.adm_user, adm_password=env.adm_password, database=None):
    """buildout the appserver, update the database and addons_list then restart the openerp service. eg. update_appserver:database=sido_dev"""
    env.user = adm_user
    env.password = adm_password

    appserver_path ="/opt/openerp/%s/%s" % (env.customer_directory, _bitbucket.appserver_repository)

    print blue("\"Stopping\" server")
    stop_openerp_service()

    print blue("\"Updating\" appserver repository")
    with cd(appserver_path):
        if _bitbucket.repository_type == "git":
            run('git pull origin master')
        else:  # Hg rocks
            run('hg pull')
            run('hg update')

    # TODO: Identify running server (gunicorn or classical openerp) 
    print blue("\"Buildouting\" server")
    with cd(appserver_path):
        run('bin/buildout')
        if database and env.addons_list:
            run('bin/start_openerp -d %s -u %s --stop-after-init' % (database, env.addons_list,))
            print green("OpenERP server updated:")
            print green("  - modules=%s" % env.addons_list)
            print green("  - database=%s" % database)
        else:
            print red("No database update:")
            if not env.addons_list:
                print red("  - no addons specified in env.addons_list")
            if not database:
                print red("  - no database specified via update_database parameter")
    
        start_openerp_service()

def ssh(user='adm_user', root_user=env.root_user, root_password=env.root_password):
    "Launch SSH session onto host"
    if user != 'adm_user':
        ssh_user = env.root_user
        ssh_password = env.root_password
    else:
        ssh_user = env.adm_user
        ssh_password = env.adm_password

    import subprocess
    print "Password= "+ blue("%s" % ssh_password)
    ssh = subprocess.call(["ssh", "-p %s" % (env.port,), "%s@%s" % (ssh_user, env.host)])
