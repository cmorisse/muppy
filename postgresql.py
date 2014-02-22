from urlparse import urlparse
from fabric.api import *
from fabric.contrib.files import exists
from fabric.colors import *
import sys

from muppy_utils import *
"""
PostgreSQL related tasks
"""

class PostgreSQLConfig:
    pass


def parse_config(config_parser):
    if config_parser.get('postgresql', 'install') and eval(config_parser.get('postgresql', 'install')):
        pass

#      _VagrantConfig.mysql_host = (config_parser.has_option('magento', 'mysql_host') \
#                                   and config_parser.get('magento', 'mysql_host')) \
#                                   or 'localhost'
#      if _MagentoConfig.api_key and not _MagentoConfig.enc_key:
#          print red("Error: missing enc_key.")
#          print red("Error: enc_key is required as you defined an api_key.")
#          sys.exit(1)

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
        run(psql_command_line)

