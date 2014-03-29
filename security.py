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
Security related tasks (ufw configuration at that time)
"""

TEMPLATE_CFG_SECTION = """
[security]
# install
# Defines wether security is setup during system install (True) or nothing is done automaticaly (False).
# In that case, user can launch security setup using muppy command: security.setup
# Allowed values are = True, 1, False, 0
#install = False

#
# trusted_ips
#
# trusted_ips:
#  - have unrestricted access on serveur.
#  - must always contains public ip of user to be able to launch setup
#  - generate "sudo ufw allow from RFC918_addr"
#       => where address is an ip or/RFC918 Networks
#trusted_ips =
#        8.8.8.8        # Office 1
#        9.9.9.9        # Office 2
#        # Customers IPs
#        10.10.10.10    # SF Office
#
trusted_ips =
#
# Parameters to grant access to specific protocol ports
# eg.
# format: PROTO RFC918_src  RFC918_dest PORT
# with:
#   - PROTO = tcp | udp | any
#   - PORT = 22 | ssh
#   - RFC918_xx = any | 192.168.0.12 | 192.168.0.12/32
#
# Example:
#allow_rules = tcp 192.168.0.12 any ssh   # comment
#              tcp 22 9.9.9.0/30 # comment
#
# Generates:
# sudo ufw allow proto {{PROTO}} from {{RFC918_src}} to {{RFC918_dest}} port {{PORT}}
allow_rules =  tcp 192.168.0.12 any ssh   # This machine has only ssh access
               tcp any          any 8069  # everybody can use OpenERP
"""

class SecurityConfig:
    enabled = False
    trusted_ips = None
    allow_rules = None


def parse_config(config_parser):
    """
    Parse muppy config file security section
    :param config_parser: A config parser of muppy cfg file.
    :type config_parser: ConfigParser.ConfigParser
    :return: a SecurityConfig object
    :rtype : SecurityConfig
    """
    if not config_parser.has_section('security'):
        return

    # install
    if config_parser.has_option('security', 'install'):
        raw_value = config_parser.get('security', 'install')
        try:
            SecurityConfig.install = eval(raw_value) or False
        except:
            print colors.red("ERROR: [security] section : \"%s\" is not a correct value for 'install' option." % raw_value)
            sys.exit(1)

    # trusted_ips is mandatory and must at least contains user ip
    if not config_parser.has_option('security', 'trusted_ips'):
        print red("trusted_ips config is required in security section !!")
        sys.exit(1)

    # will decompose in case we will be back on this
    raw_trusted_ips = config_parser.get('security', 'trusted_ips')
    raw_trusted_ips = filter(None, raw_trusted_ips.split('\n'))  # split on each line filtering empty ones
    raw_trusted_ips = filter(None, [e.split('#')[0].strip() for e in raw_trusted_ips])  # build a list of ips by removing comment, filtering on empty
    SecurityConfig.trusted_ips = raw_trusted_ips

    raw_allow_rules = config_parser.get('security', 'allow_rules')
    raw_allow_rules = filter(None, raw_allow_rules.split('\n'))
    raw_allow_rules = [line.split('#')[0] for line in raw_allow_rules]
    raw_allow_rules = [filter(None, line.split(' ')) for line in raw_allow_rules]
    SecurityConfig.allow_rules = raw_allow_rules

    SecurityConfig.enabled = True
    return SecurityConfig


def get_current_ip():
    """
    Retreive current ip address from two distinct source

    :return: numerical IP address as a string
    :rtype: IP as str or None if all services failed
    """
    ip_regex = re.compile('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    services = [
        "http://bot.whatismyipaddress.com",
        "http://ip4.telize.com"
    ]

    checked_ips = []
    for service in services:
        try:
            ip = requests.get(service).text.strip()
            if ip_regex.match(ip) and ip not in checked_ips:
                checked_ips.append(ip)
        except:
            pass

    if len(checked_ips) == 1:
        return checked_ips[0]
    return None

@task
def setup():
    """:[[database]] - Open PSQL and connect to the 'postgres' database or [[database]] if supplied"""
    env.user, env.password = env.root_user, env.root_password
    if not SecurityConfig.enabled:
        print red("ERROR: Security is disabled in config file")
        sys.exit(1)

    current_ip = get_current_ip()
    if not current_ip:
        print red("ERROR: Unable to retreive current public IP. Aborting.")
        sys.exit(1)

    if current_ip not in SecurityConfig.trusted_ips:
        print red("ERROR: Current public IP is not in 'trusted_ips' list. Aborting.")
        sys.exit(1)

    sudo("yes | ufw reset")
    for trusted_ip in SecurityConfig.trusted_ips:
        sudo("ufw allow from %s" % trusted_ip)

    for rule in SecurityConfig.allow_rules:
        sudo("ufw allow proto %s from %s to %s port %s" % (rule[0], rule[1], rule[2], rule[3],))
    sudo("yes | ufw enable")

@task
def disable():
    """Disable firewall on server"""
    env.user, env.password = env.root_user, env.root_password
    sudo("ufw disable")

@task
def enable():
    """Enale firewall on server. Warning this commande don't do any setup."""
    env.user, env.password = env.root_user, env.root_password
    sudo("yes | ufw enable")

@task
def status():
    """Show current firewall status."""
    env.user, env.password = env.root_user, env.root_password
    sudo("ufw status numbered verbose")

@task
def generate_config_template():
    """Generate a template [security] section to add in a muppy config file."""
    print TEMPLATE_CFG_SECTION
