from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists
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
# In that case locale is ignored whatever value it is.
"""


class SystemConfig:
    install = False
    locale = None


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

    # will decompose in case we will be back on this
    raw_locale = config_parser.get('system', 'locale')
    SystemConfig.locale = raw_locale

    return SystemConfig

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

    # We check locale is a validone
    ret_val = sudo("locale-gen %s" % locale, quiet=True, warn_only=True)
    if ret_val.failed:
        print colors.red("ERROR: Unable to generate locale '%s'." % locale)
        sys.exit(1)

    language = locale.split('.')[0]
    ret_val = sudo('update-locale LANG="%s" LANGUAGE="%s" LC_ALL="%s" LC_CTYPE="%s"' % (locale, language, locale, locale,), quiet=True, warn_only=True)
    if ret_val.failed:
        print colors.red("ERROR: Unable to update-locale with '%s'." % locale)
        sys.exit(1)

    ret_val = sudo('dpkg-reconfigure locales', quiet=True, warn_only=True)
    if ret_val.failed:
        print colors.red("ERROR: Unable to 'sudo dpkg-reconfigure locales'.")
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