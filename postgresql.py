from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists, append
from fabric.colors import *
import sys
import string

from muppy_utils import *
from system import get_system_version

"""
PostgreSQL related tasks
"""

TEMPLATE_CFG_SECTION = """

[postgresql]
# Serveur Version (9.4 or default)
#version = default
#
# Automated daily backup
# Muppy contains a postgresql backup script that can be installed and setup in CRON
#
# backup_root_directory
# backup files are stored in {{backup_root_directory}}/data
# backup scripts are stored in {{backup_root_directory/scripts}}
#backup_root_directory={{env.backup_directory}}

#
# backup_email_recipients
# Each time it runs, the backup script mails the backup log to the following recipients
# if undefined, backup log is not sent ; but just stored in the backup data directory
# Note that muppy do not install nor configure postfix
# recients are comma separated. eg. cmo@domain.com,aba@domain.net
#backup_email_recipients =

# The number of days each backup file is kept before it is deleted
#backup_retention_period_in_days = 7

# The cron values.
# By default backup is launched at 2:00 every day
#backup_cron_m_h_dom_mon_dow = "00 2 * * *"

#
# activate_dropbox_integration
# Defines if backup script will update backup files to Dropbox.
# Note that this option requires extra configuration steps
#activate_dropbox_integration = False

#
# target_scp_servers
# If set with a valid muppy hostname that accept ssh passwordless connection,
# backup script will scp each database backup file to this server.
# target_scp_servers=10.0.0.2


"""


class PostgreSQLConfig:
    pass


def parse_config(config_parser):
    # Automated daily backup options
    PostgreSQLConfig.version = (config_parser.has_option('postgresql', 'version') and config_parser.get('postgresql', 'version')) or 'default'
    PostgreSQLConfig.backup_root_directory = (config_parser.has_option('postgresql', 'backup_root_directory') and config_parser.get('postgresql', 'backup_root_directory')) or env.backup_directory
    PostgreSQLConfig.backup_email_recipients = (config_parser.has_option('postgresql', 'backup_email_recipients') and config_parser.get('postgresql', 'backup_email_recipients')) or ''
    PostgreSQLConfig.backup_retention_period_in_days = (config_parser.has_option('postgresql', 'backup_retention_period_in_days') and config_parser.get('postgresql', 'backup_retention_period_in_days')) or 7
    PostgreSQLConfig.backup_cron_m_h_dom_mon_dow = (config_parser.has_option('postgresql', 'backup_cron_m_h_dom_mon_dow') and config_parser.get('postgresql', 'backup_cron_m_h_dom_mon_dow')) or "00 2 * * *"
    PostgreSQLConfig.activate_dropbox_integration = (config_parser.has_option('postgresql', 'activate_dropbox_integration') and config_parser.get('postgresql', 'activate_dropbox_integration')) or False
    PostgreSQLConfig.target_scp_servers = (config_parser.has_option('postgresql', 'target_scp_servers') and config_parser.get('postgresql', 'target_scp_servers')) or False

    PostgreSQLConfig.backup_files_directory = os.path.join(PostgreSQLConfig.backup_root_directory, 'postgresql')
    PostgreSQLConfig.backup_scripts_directory = os.path.join(PostgreSQLConfig.backup_root_directory, 'scripts')
    PostgreSQLConfig.backup_script_path = os.path.join(PostgreSQLConfig.backup_scripts_directory, 'muppy_backup_all_postgresql_databases.sh')

    return PostgreSQLConfig


@task
def psql(database='postgres'):
    """:[[database]] - Open PSQL and connect to the 'postgres' database or [[database]] if supplied"""
    env.user = env.adm_user
    env.password = env.adm_password

    psql_command_line = "export PGPASSWORD='%s' && psql -h %s -p %s -U %s %s" % (env.db_password, env.db_host, env.db_port, env.db_user, database)
    print magenta("Connecting to database '%s' on server '%s'" % (database, env.db_host))
    print magenta("Using command: %s" % psql_command_line)
    env_output_prefix_backup = env.output_prefix
    env.output_prefix = ''
    with hide('running'):
        open_shell(psql_command_line)



@task
def get_databases_list(embedded=False):
    """Returns list of existing databases on server"""
    # 'psql -h localhost -U openerp --no-align --pset footer -t -c "SELECT datname FROM pg_database WHERE datistemplate = FALSE ;" postgres'
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password
    get_databases_cl = 'export PGPASSWORD="%s" && psql -h %s -p %s -U %s --no-align --pset footer -t -c "SELECT datname FROM pg_database;" postgres' % ( env.db_password, env.db_host, env.db_port, env.db_user)
    command = run(get_databases_cl, quiet=True)

    env.user, env.password = env_backup
    if command.succeeded:
        if not embedded:
            db_list = command.split('\r\n')
            print
            for db in db_list:
                print db
        return command.split('\r\n')
    return []

def local_get_databases_list():
    """Returns list of existing databases on local database server"""
    get_databases_cl = 'export PGPASSWORD="%s" && psql -h %s -U %s --no-align --pset footer -t -c "SELECT datname FROM pg_database;" postgres' % ( env.db_password, env.db_host, env.db_user)
    command = local(get_databases_cl, capture=True)
    if command.succeeded:
        return command.split('\n')
    return []


@task
def backup(database, backup_file_name=None):
    """:database - Backup database and put backup file into {{backup_files_directory}} using a muppy generated backup name"""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    if not database:
        print red("ERROR: missing required database parameter.")
        exit(128)

    if not backup_file_name:
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        hostname = get_hostname()
        backup_file_name = os.path.join(env.postgresql.backup_files_directory, "%s__%s__%s.pg_dump" % (timestamp, database, hostname,))

    backup_command_line = "export PGPASSWORD='%s' && pg_dump -Fc -h %s -p %s -U %s -f%s %s" % ( env.db_password, env.db_host, env.db_port, env.db_user, backup_file_name, database,)
    run(backup_command_line)

    env.user, env.password = env_backup


@task
def local_backup(database, backup_file_name=None):
    """:database - Backup database and put backup file into muppy directory using a muppy generated backup name"""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    if not database:
        print red("ERROR: missing required database parameter.")
        exit(128)

    if not backup_file_name:
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        hostname = get_local_hostname()
        local('mkdir -p backups/%s' % hostname)
        backup_file_name = os.path.join('backups/%s' % hostname, "%s__%s__%s.pg_dump" % (timestamp, database, hostname,))

    backup_command_line = "export PGPASSWORD='%s' && pg_dump -Fc -h %s -p %s -U %s -f%s %s" % ( env.db_password, env.db_host, env.db_port, env.db_user, backup_file_name, database,)
    local(backup_command_line)

    env.user, env.password = env_backup

@task
def local_restore(backup_file_path, new_database_name=None, jobs=4):
    """:backup_file_path,[new_database_name] - Restore a database using specified backup file path absolute or relative from muppy working directory."""

    if not backup_file_path:
        print red("ERROR: missing required backup_file parameter.")
        exit(0)

    if not os.path.exists(backup_file_path):
        print red("ERROR: missing '%s' backup file." % backup_file_path)
        exit(0)

    (timestamp, database, host,) = os.path.basename(backup_file_path).split('.')[0].split('__')

    # use new database name if specified
    database = new_database_name or database

    if database in local_get_databases_list():
        dropdb_command_line = "export PGPASSWORD='%s' && dropdb -h %s -U %s %s" % (env.db_password, env.db_host, env.db_user, database,)
        local(dropdb_command_line)

    createdb_command_line = "export PGPASSWORD='%s' && createdb -h %s -U %s %s 'Restored by Muppy'" % (env.db_password, env.db_host, env.db_user, database,)
    local(createdb_command_line)
    
    try:
        jobs_number = int(jobs)
        jobs_option = '--jobs=%s' % jobs_number
    except Exception:
        jobs_option = ''

    # Warning:
    restore_command_line = "export PGPASSWORD='%s' && pg_restore -h %s -U %s --no-owner %s -d %s %s"\
                           % (env.db_password, env.db_host, env.db_user, jobs_option, database, backup_file_path,)
    local(restore_command_line)


@task
def restore(backup_file, new_database_name=None, jobs=4):
    """:backup_file,[new_database_name] - Restore a database using specified backup file stored in {{backup_directory}}."""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    if not backup_file:
        print red("ERROR: missing required backup_file_name parameter.")
        exit(0)

    backup_file_path = os.path.join(env.postgresql.backup_files_directory, backup_file)
    if not exists(backup_file_path):
        print red("ERROR: missing '%s' backup file." % backup_file_path)
        exit(0)

    (timestamp, database, host,) = backup_file.split('.')[0].split('__')

    # use new database name if specified
    database = new_database_name or database

    if database in get_databases_list(embedded=True):
        dropdb_command_line = "export PGPASSWORD='%s' && dropdb -h %s -U %s %s"\
                              % (env.db_password, env.db_host, env.db_user, database,)
        run(dropdb_command_line)

    createdb_command_line = "export PGPASSWORD='%s' && createdb -h %s -U %s %s 'Restored by Muppy'" % (env.db_password, env.db_host, env.db_user, database,)
    run(createdb_command_line)

    try:
        jobs_number = int(jobs)
        jobs_option = '--jobs=%s' % jobs_number
    except Exception:
        jobs_option = ''

    restore_command_line = "export PGPASSWORD='%s' && pg_restore -h %s -U %s --no-owner %s -d %s %s" \
                           % (env.db_password, env.db_host, env.db_user, jobs_option, database, backup_file_path,)
    run(restore_command_line)

    env.user, env.password = env_backup
    return


@task
def list_backups():
    """List files in {{backup_directory}}."""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    run("ls -l %s" % (env.postgresql.backup_files_directory,))

    env.user, env.password = env_backup
    return


@task
def get_backup_file(backup_file, local_path="backups/%(host)s/%(path)s"):
    """:backup_file - Download a backup_file from {{backup_files_directory}} into ./backups/%(host)s/%(path)s"""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    if not backup_file:
        print red("ERROR: missing required backup_file parameter")
        exit(0)

    backup_file_path = os.path.join(env.postgresql.backup_files_directory, backup_file)

    if not exists(backup_file_path):
        print red("ERROR: backup file '%s' does not exist." % backup_file)
        exit(0)

    get(backup_file_path, local_path)

    env.user, env.password = env_backup
    return


@task
def put_backup_file(local_backup_file_path=None, force=False):
    """:backup_file[[,force]] - Upload <<backup_file>> to {{ppostgresql.backup_files_directory}}. Fail if local_backup_file does not exist or remote backup file exists unless force=True is specified."""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    if not local_backup_file_path or not os.path.isfile(local_backup_file_path):
        print red("ERROR: missing required local_backup_file")
        exit(0)

    remote_backup_file_path = os.path.join(env.postgresql.backup_files_directory,
                                           os.path.basename(local_backup_file_path))

    if exists(remote_backup_file_path):
        if not force:
            print red("ERROR: backup file '%s' already exists in "
                      "remote server backup directory. use force=True "
                      "to overwrite it." % os.path.basename(local_backup_file_path))
            exit(0)
        confirm = prompt("Are you sure you want to upload '%s' on server '%s'. Enter YES to confirm." % (os.path.basename(local_backup_file_path), get_hostname(),), default="no", validate="YES|no")
        if confirm != 'YES':
            print red("Upload aborted ; remote file untouched.")
            sys.exit(126)
    print "local_backup_file_path=%s" % local_backup_file_path
    print "remote_backup_file_path=%s" % remote_backup_file_path
    put(local_backup_file_path, remote_backup_file_path)

    env.user, env.password = env_backup
    return


#
# Due to bash syntax we cannot use Jinja or python string
# interpolation syntax.
# So we build our own string.Template class using '_@@' as delimiter
#
class MuppyTemplate(string.Template):
    delimiter = '_@@'


@task
def install_backup_script():
    """Installs and configure PostgreSQL daily backup script"""
    env.user = env.adm_user
    env.password = env.adm_password

    run('mkdir -p %s' % env.postgresql.backup_scripts_directory)
    run('mkdir -p %s/postgresql' % env.postgresql.backup_root_directory, quiet=True)

    template_context = {
        'backup_root_directory': env.postgresql.backup_root_directory,
        'backup_files_directory': env.postgresql.backup_files_directory,
        'backup_email_recipients': env.postgresql.backup_email_recipients,
        'backup_retention_period_in_days': env.postgresql.backup_retention_period_in_days,
        'activate_dropbox_integration': env.postgresql.activate_dropbox_integration,
        'target_scp_servers': env.postgresql.target_scp_servers,
        'pg_user': env.db_user,
        'pg_password': env.db_password,
    }

    template_file = open('scripts/muppy_backup_all_postgresql_databases.sh')
    template_script = template_file.read()
    mt = MuppyTemplate(template_script)
    final_script = StringIO.StringIO(mt.substitute(template_context))

    put(local_path=final_script, remote_path=env.postgresql.backup_script_path, mode='774')


@task
def install_backup_cron():
    """Add muppy postgresql backup script to a daily cron (needs a postgresql.install_backup_script before)"""
    env.user = env.adm_user
    env.password = env.adm_password

    # To debug cron, add a MAILTO=email@domain.ext in crontab
    command_str = 'cat <(crontab -l) <(echo "%s %s") | crontab -'\
                  % (env.postgresql.backup_cron_m_h_dom_mon_dow, env.postgresql.backup_script_path,)
    run(command_str, warn_only=True)


@task
def generate_config_template():
    """Generate a template [postgresql] section that you can copy paste into muppy config file."""
    print TEMPLATE_CFG_SECTION

@task
def install(version="default"):
    """:[version=9.3] Install postgresql specified version or the version defined in config file."""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password
    if version == 'default':
        version = PostgreSQLConfig.version
    
    full_version = get_system_version()
    system_version = full_version['os_version']
    if system_version == "18.04":
        result = sudo('grep "apt.postgresql.org" /etc/apt/sources.list.d/pgdg.list', quiet=True)
        if result.return_code:
            print cyan("Adding PostgreSQL repository to apt sources list.")
            sudo('wget -q https://www.postgresql.org/media/keys/ACCC4CF8.asc -O - | sudo apt-key add -')
            sudo('echo \"deb http://apt.postgresql.org/pub/repos/apt/ %s-pgdg main\" > /etc/apt/sources.list.d/pgdg.list' % full_version['os_version_codename'])
            sudo('apt update')
        
        if version=='default':
            version = "10"

        print cyan("Installation PostgreSQL %s from PostgreSQL official repository." % version)
        sudo("apt install -y postgresql-%s postgresql-contrib-%s" % (version, version,))

    else:
        if version == '9.4':
            if not exists('/etc/apt/sources.list.d/pgdg.list', use_sudo=True):
                append('/etc/apt/sources.list.d/pgdg.list',
                       'deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main',
                       use_sudo=True)
                sudo("wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add - ")
                sudo('sudo apt-get update --fix-missing')
    
            sudo('apt-get install -y postgresql-9.4')
        
        elif version == '9.5':
            if env.system.distribution == 'ubuntu':
                if env.system.version == '16.04':
                    sudo('sudo apt-get update --fix-missing')                
                    sudo('apt-get install -y postgresql-9.5')
                
                elif env.system.version == '14.04':
                    print red("PostgreSQL 9.5 installation on Ubuntu '%s' is not implemented. Installation aborted." % env.system.version)
                    exit(128)
            else:
                print red("Dont't know how to install PostgreSQL on '%s'. Installation aborted.")
                exit(128)
        else:
            sudo('sudo apt-get update --fix-missing')
            sudo('apt-get install -y postgresql')

    env.user, env.password = env_backup
    print green("PosgreSQL server and client installed.")


# Install postgresql 9.4 on Ubuntu
# voir http://www.postgresql.org/download/linux/ubuntu/
# Sur trusty
# AJouter la ligne suivante dans le fichier: /etc/apt/sources.list.d/pgdg.list
# deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main
#
#wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
#sudo apt-get update
#apt-get install postgresql-9.4






