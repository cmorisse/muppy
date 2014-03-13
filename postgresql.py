from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists
from fabric.colors import *
import sys
import string

from muppy_utils import *
"""
PostgreSQL related tasks
"""


class PostgreSQLConfig:
    pass


def parse_config(config_parser):
    # Automated daily backup options
    PostgreSQLConfig.backup_root_directory = (config_parser.has_option('postgresql', 'backup_root_directory') and config_parser.get('postgresql', 'backup_root_directory')) or env.backup_directory
    PostgreSQLConfig.backup_email_recipients = (config_parser.has_option('postgresql', 'backup_email_recipients') and config_parser.get('postgresql', 'backup_email_recipients')) or ''
    PostgreSQLConfig.backup_retention_period_in_days = (config_parser.has_option('postgresql', 'backup_retention_period_in_days') and config_parser.get('postgresql', 'backup_retention_period_in_days')) or 120
    PostgreSQLConfig.backup_cron_m_h_dom_mon_dow = (config_parser.has_option('postgresql', 'backup_cron_m_h_dom_mon_dow') and config_parser.get('postgresql', 'backup_cron_m_h_dom_mon_dow')) or "00 2 * * *"
    PostgreSQLConfig.activate_dropbox_integration = (config_parser.has_option('postgresql', 'activate_dropbox_integration') and config_parser.get('postgresql', 'activate_dropbox_integration')) or False

    PostgreSQLConfig.backup_files_directory = os.path.join(PostgreSQLConfig.backup_root_directory, 'postgresql')
    PostgreSQLConfig.backup_scripts_directory = os.path.join(PostgreSQLConfig.backup_root_directory, 'scripts')
    PostgreSQLConfig.backup_script_path = os.path.join(PostgreSQLConfig.backup_scripts_directory, 'muppy_backup_all_postgresql_databases.sh')

    return PostgreSQLConfig


@task
def psql(database='postgres'):
    """:[[database]] - Open PSQL and connect to the 'postgres' database or [[database]] if supplied"""
    env.user = env.adm_user
    env.password = env.adm_password

    psql_command_line = "export PGPASSWORD='%s' && psql -h localhost -U %s %s" % (env.db_password, env.db_user, database)
    print magenta("Connecting to database '%s' on server '%s'" % (database, env.host))
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
    get_databases_cl = 'export PGPASSWORD="%s" && psql -h %s -U %s --no-align --pset footer -t -c "SELECT datname FROM pg_database;" postgres' % ( env.db_password, env.db_host, env.db_user)
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

    backup_command_line = "export PGPASSWORD='%s' && pg_dump -Fc -h %s -U %s -f%s %s" % ( env.db_password, env.db_host, env.db_user, backup_file_name, database,)
    run(backup_command_line)

    env.user, env.password = env_backup


@task
def local_restore(backup_file_path, jobs=4):
    """:backup_file_path - Restore a database using specified backup file path absolute or relative from muppy working directory."""

    if not backup_file_path:
        print red("ERROR: missing required backup_file parameter.")
        exit(0)

    if not os.path.exists(backup_file_path):
        print red("ERROR: missing '%s' backup file." % backup_file_path)
        exit(0)

    (timestamp, database, host,) = os.path.basename(backup_file_path).split('.')[0].split('__')

    if database in local_get_databases_list():
        dropdb_command_line = "export PGPASSWORD='%s' && dropdb -h %s -U %s %s" % (env.db_password, env.db_host, env.db_user, database,)
        local(dropdb_command_line)

    try:
        jobs_number = int(jobs)
        jobs_option = '--jobs=%s' % jobs_number
    except Exception:
        jobs_option = ''

    restore_command_line = "export PGPASSWORD='%s' && pg_restore -h %s -U %s %s --create -d postgres %s" % ( env.db_password, env.db_host, env.db_user, jobs_option, backup_file_path,)
    local(restore_command_line)



@task
def restore(backup_file, jobs=4):
    """:backup_file - Restore a database using specified backup file stored in {{backup_directory}}."""
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

    if database in get_databases_list(embedded=True):
        dropdb_command_line = "export PGPASSWORD='%s' && dropdb -h %s -U %s %s" % (env.db_password, env.db_host, env.db_user, database,)
        run(dropdb_command_line)

    try:
        jobs_number = int(jobs)
        jobs_option = '--jobs=%s' % jobs_number
    except Exception:
        jobs_option = ''

    restore_command_line = "export PGPASSWORD='%s' && pg_restore -h %s -U %s %s --create -d postgres %s" % ( env.db_password, env.db_host, env.db_user, jobs_option, backup_file_path,)
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

    remote_backup_file_path = os.path.join(env.postgresql.backup_files_directory, os.path.basename(local_backup_file_path))

    if exists(remote_backup_file_path):
        if not force:
            print red("ERROR: backup file '%s' already exists in remote server backup directory. use force=True to overwrite it." % os.path.basename(local_backup_file_path))
            exit(0)
        confirm = prompt("Are you sure you want to upload '%s' on server '%s'. Enter YES to confirm." % (os.path.basename(local_backup_file_path), get_hostname(),), default="no", validate="YES|no")
        if confirm != 'YES':
            print red("Upload aborted ; remote file untouched.")
            sys.exit(126)

    put(local_backup_file_path, env.postgresql.backup_files_directory)

    env.user, env.password = env_backup
    return



#
# Due to bash syntax syntax we cannot use Jinja or python string
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
    run('cat <(crontab -l) <(echo "%s %s") | crontab -' % (env.postgresql.backup_cron_m_h_dom_mon_dow, env.postgresql.backup_script_path), warn_only=True)
