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
    """Add muppy postgresql backup script to a daily cron"""
    env.user = env.adm_user
    env.password = env.adm_password

    # To debug cron, add a MAILTO=email@domain.ext in crontab
    run('cat <(crontab -l) <(echo "%s %s") | crontab -' % (env.postgresql.backup_cron_m_h_dom_mon_dow, env.postgresql.backup_script_path), warn_only=True)
