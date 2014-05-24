from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib import files
from fabric import colors
import sys
import string
import requests

from muppy_utils import *
import system

#TODO: Allow password authentication except for ubuntu
# Add to /etc/ssh/sshd_config
#PasswordAuthentication no
#...
# Add to end of file
#Match User admmathon
#    PasswordAuthentication yes


"""
Muppy LXC Integration
"""
MUPPY_LXC_PREFIX = ''  # reserved for futur use

TEMPLATE_CFG_SECTION = """
[lxc]
# install
# Defines wether lxc configuration is done during system install (True) or not  (False).
# In that case, user can launch lxc setup using muppy command: lxc.setup
# Allowed values are = True, 1, False, 0
#install = False

#
# user_name
#
# Name of the user who will own all unprivileged containers.
#user_name='leech'

#
# user_password
#
# Password for LXC user_name
#user_password=user_name

#
# max_network_interfaces_per_user
#
# Maximum number of interfaces that can be created for containers by user_name
# Implicitly defines the maximum numbers of containers that can be created by user_name
# given they have at least one net interface
#max_network_interfaces_per_user = 80

#
# public_interface
#
# Name of the interface connected to public network.
#public_interface=eth0

#
# ssh_pwauth (Not implemented)
# cloud-init parameter to allow or not ssh password authentication.
#ssh_pwauth = True

#
# admin_ssh_keys (Required)
#
# List of ssh public keys to authenticate user able to log as 'user_name'
#
# Examples
# admin_ssh_keys =
    ssh-rsa AAAAdddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd cinder@ello
    ssh-rsa AAAAB3NzaC1yc2EAAAADAsvvsvvdvbdvbdbvdghenlkhlklkhhkjllhkhlklkhlkhlkhklhkjkjljklllllllllllllllllllllllllllllllllllllllllllllllkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkl cinder@ella
#
#admin_ssh_key =


published_ports = ...
# under development

"""


class LXCConfig:
    def __init__(self):
        pass

    enabled = False
    # named after one of the Troll in 'Tinker Bell and the Lost Treasure'
    # See http://disneyfairies.wikia.com/wiki/Troll
    install = False
    user_name = 'leech'
    user_password = None
    max_network_interfaces_per_user = 80  # So it's 50 Containers max
    public_interface = 'eth0'
    
    ssh_pwauth = True  
    # To make this an effective parameter, we must add the ability to specify 
    # an authorized_keys list for adm_user
    #TODO: add an authorized_keys param for adm_user


def parse_config(config_parser):
    """
    Parse muppy config file lxc section
    :param config_parser: A config parser of muppy cfg file.
    :type config_parser: ConfigParser.ConfigParser
    :return: a LXCConfig object
    :rtype : LXCConfig
    """
    if not config_parser.has_section('lxc'):
        return

    # install
    if config_parser.has_option('lxc', 'install'):
        raw_value = config_parser.get('lxc', 'install')
        try:
            LXCConfig.install = eval(raw_value) or False
        except:
            print colors.red("ERROR: [lxc] section : \"%s\" is not a correct value for 'install' option." % raw_value)
            sys.exit(1)

    # user_name : defaults to 'leech'
    if config_parser.has_option('lxc', 'user_name'):
        raw_user_name = config_parser.get('lxc', 'user_name')
        if raw_user_name:
            LXCConfig.user_name = raw_user_name

    # user_password : defaults to user_name
    if config_parser.has_option('lxc', 'user_password'):
        raw_user_password = config_parser.get('lxc', 'user_password')
        if raw_user_password:
            LXCConfig.user_password = raw_user_password
    else:
        LXCConfig.user_password = LXCConfig.user_name

    # public_interface : defaults to 'eth0'
    if config_parser.has_option('lxc', 'public_interface'):
        raw_public_interface = config_parser.get('lxc', 'public_interface')
        if raw_public_interface:
            LXCConfig.public_interface = raw_public_interface

    # noinspection PyBroadException
    try:
        LXCConfig.max_network_interfaces_per_user = config_parser.get('lxc', 'max_network_interfaces_per_user')
    except:
        pass

    # admin_ssh_keys is mandatory
    if not config_parser.has_option('lxc', 'admin_ssh_keys') or not config_parser.get('lxc', 'admin_ssh_keys'):
        print red("admin_ssh_keys is required in [lxc] section of '%s' config file !!" % env.config_file)
        sys.exit(1)

    # will decompose in case we will be back on this
    raw_admin_ssh_keys = config_parser.get('lxc', 'admin_ssh_keys')
    raw_admin_ssh_keys = filter(None, raw_admin_ssh_keys.split('\n'))  # split on each line filtering empty ones
    LXCConfig.admin_ssh_keys = raw_admin_ssh_keys

    # published_ports_list for automated republication (at reboot)
    if config_parser.has_option('lxc', 'published_ports') and config_parser.get('lxc', 'published_ports'):
        # decompose in case we will be back on this
        raw_published_port_list = config_parser.get('lxc', 'published_ports')
        raw_published_port_list = filter(None, raw_published_port_list.split('\n'))  # split on each line filtering empty ones
        raw_published_port_list = [(p.split(',')[0], p.split(',')[1], p.split(',')[2],) for p in raw_published_port_list]

        LXCConfig.published_ports_list = raw_published_port_list
    else:
        LXCConfig.published_ports_list = []

    LXCConfig.enabled = True
    return LXCConfig


@task
def generate_config_template():
    """Generate a template [lxc] section to add in a muppy config file."""
    print TEMPLATE_CFG_SECTION


@task
def setup(disable_password_auth=False):
    """Install Muppy LXC Infrastructure."""
    be_quiet = False
    # Note: This task is idempotent
    env.user, env.password = env.root_user, env.root_password

    if not LXCConfig.enabled:
        print red("ERROR: LXC is disabled in config file")
        sys.exit(1)

    # install lxc
    # we add whois as we need mkpasswd
    sudo("apt-get install -y lxc whois", quiet=be_quiet)
    print colors.blue("INFO: lxc installed.")

    # containers owner user
    system.user_create(env.lxc.user_name, env.lxc.user_password, quiet=be_quiet)
    print colors.blue("INFO: '%s' user created." % env.lxc.user_name)

    # upload ssh keys
    system.user_set_ssh_authorized_keys(env.lxc.user_name, env.lxc.user_password, env.lxc.admin_ssh_keys, quiet=be_quiet)
    print colors.blue("INFO: SSH keys uploaded to user '%s' account." % env.lxc.user_name)

    # disable password auth for server
    if disable_password_auth:
        if not files.contains('/etc/ssh/sshd_config', "PasswordAuthentication no", use_sudo=True):
            files.append('/etc/ssh/sshd_config', "PasswordAuthentication no", use_sudo=True)
    else:
        if files.contains('/etc/ssh/sshd_config', "PasswordAuthentication no", use_sudo=True):
            # TODO: implement
            print red("CRITICAL: You must manually remove the line 'PasswordAuthentication no' from /etc/ssh/sshd_config.")

    # retreive sub user ids and group ids
    sub_ids = system.user_get_sub_ids(LXCConfig.user_name, quiet=be_quiet)
    # create user default container configuration file
    env.user, env.password = env.lxc.user_name, env.lxc.user_password
    run("mkdir -p ~/.config/lxc", quiet=be_quiet)
    lxc_default_conf_cmd = """cat > ~/.config/lxc/default.conf <<EOF
lxc.network.type = veth
lxc.network.link = lxcbr0
lxc.id_map = u 0 %s %s
lxc.id_map = g 0 %s %s
EOF""" % sub_ids
    run(lxc_default_conf_cmd, quiet=be_quiet)
    print colors.blue("INFO: '%s' default container configuration updated." % env.lxc.user_name)

    # grant network bridge access to lxc user
    env.user, env.password = env.root_user, env.root_password
    lxc_usernet_filename = '/etc/lxc/lxc-usernet'
    regex_str = "%s[ \t]*veth[ \t]*lxcbr0.*$" % env.lxc.user_name

    # we don't use contains() as it echoes garbage
    #if files.contains(lxc_usernet_filename, "%-10s veth lxcbr0" % env.lxc.user_name, use_sudo=True):
    if sudo("grep '%s' %s" % (regex_str, lxc_usernet_filename,), quiet=be_quiet, warn_only=True).succeeded:
        # we remove all lines
        sudo("sed -i.bak '/%s/d' %s" % (regex_str, lxc_usernet_filename,), quiet=be_quiet, warn_only=True)
    # same thing for append
    #files.append(lxc_usernet_filename, "%-10s veth lxcbr0 %5s" % (env.lxc.user_name, env.lxc.max_network_interfaces_per_user,), use_sudo=True)
    sudo("echo '%-10s veth lxcbr0 %5s' >> %s" % (env.lxc.user_name, env.lxc.max_network_interfaces_per_user, lxc_usernet_filename,), quiet=be_quiet, warn_only=True)

    print colors.blue("INFO: '%s' allowed to use %s network interfaces in all containers." % (env.lxc.user_name, env.lxc.max_network_interfaces_per_user,))

    print colors.green("Muppy LXC Configuration done.")
    return


def generate_ssh_keys(y_prefix, keys):
    return ''.join([y_prefix+"- %s \n" % key for key in keys])


@task
def create(name, release, password, ssh_key=None, locale='fr_FR.UTF-8'):
    """:name,release,password,ssh_key,locale="fr_FR.UTF-8" - Create a container {{name}} of ubuntu {{release}}, Set {{password}} to ubuntu user and add {{sshkey}} if supplied. (note that ssh password auth is disabled for user ubuntu)."""
    # We use cloud-image templates as we can use cloud-init to configure container
    # we create on cloud-init file per container stored in lxc.user_name home
    # See. https://code.launchpad.net/~cloud-init-dev/cloud-init/trunk
    env.user, env.password = env.lxc.user_name, env.lxc.user_password

    #
    # Generate cloudinit
    #
    # We configure container so that:
    #   - root user is ubuntu
    #   - ubuntu password is set the {{password}} parameter
    #   - ssh_admin_keys are injected into ubuntu ssh authorized_keys
    #
    ssh_keys = env.lxc.admin_ssh_keys
    if ssh_key:
        ssh_keys += [ssh_key]

    cloudinit_data_generation_cmd = """cat > cloudinit-userdata-%(name)s <<EOF
#cloud-config
locale: %(locale)s
# 1) Password definition
# On unprivileged container, password definition is required before sshkey injection (see below)
# We disable ssh password auth as it's to dangerous
password: %(password)s
chpasswd: { expire: False }
ssh_pwauth: %(ssh_pwauth)s
# 2) ssh admin keys definition
# Note: ssh key injection fails on unprivileged container if password is not defined before
ssh_authorized_keys:
%(admin_ssh_keys)s
EOF""" % {
        'name': name,
        'password': password,
        'locale': locale,
        'admin_password': env.lxc.user_password,
        'ssh_pwauth': env.lxc.ssh_pwauth,
        'admin_ssh_keys': generate_ssh_keys('   ', ssh_keys),
    }

    run(cloudinit_data_generation_cmd, quiet=False)

    #
    # create container
    #
    create_container_cmd = "lxc-create -n %(name)s -t ubuntu-cloud --" \
                           " -r %(release)s --userdata=cloudinit-userdata-%(name)s" % {
                                'name': name,
                                'release': release
                           }
    run(create_container_cmd, quiet=False)
    start(name)
    return


#TODO: to finish ?
#@task
def create_new(name, release, username, ssh_key=None, locale='fr_FR.UTF-8'):
    """:name,release, username,ssh_key,locale="fr_FR.UTF-8" - Create a container named after {{name}} of {{release}} and a sudo account with {{username}} and {{sshkey}} (no password auth)."""
    # We use cloud-image templates as we can use cloud-init to configure container
    # we create on cloud-init file per container stored in lxc.user_name home
    # See. https://code.launchpad.net/~cloud-init-dev/cloud-init/trunk
    env.user, env.password = env.lxc.user_name, env.lxc.user_password

    #
    # Generate cloudinit
    #
    # We configure container so that:
    #   - root user is ubuntu
    #   - ubuntu password is defined by the {{password}} parameter
    #   - ssh_admin_keys are injected into ubuntu authorized keys
    cloudinit_data_generation_cmd = """cat > cloudinit-userdata-%(name)s <<EOF
#cloud-config
locale: %(locale)s
# 1) Password definition
# On unprivileged container, password definition is required before sshkey injection (see below)
# We disable ssh password auth as it's to dangerous
password: %(admin_password)s
chpasswd: { expire: False }
ssh_pwauth: False
# 2) ssh admin keys definition
# Note: ssh key injection fails on unprivileged container if password is not defined before
ssh_authorized_keys:
%(admin_ssh_keys_1)s
users:
  - default
  - name: %(username)s
    gecos: %(username)s
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: users, admin
    ssh-import-id: None
    lock-passwd: false
    ssh-authorized-keys:
%(admin_ssh_keys_2)s""" % {
        'name': name,
        'username': username,
        'locale': locale,
        'admin_password': env.lxc.user_password,
        'admin_ssh_keys_1': generate_ssh_keys('   ', env.lxc.admin_ssh_keys),
        'admin_ssh_keys_2': generate_ssh_keys('      ', env.lxc.admin_ssh_keys),
    }
    if ssh_key:
        cloudinit_data_generation_cmd += "      - %s\n" % ssh_key
    cloudinit_data_generation_cmd += "EOF"
    run(cloudinit_data_generation_cmd, quiet=False)

    #
    # create container
    #
    create_container_cmd = "lxc-create -n %(name)s -t ubuntu-cloud --" \
                           " -r %(release)s --userdata=cloudinit-userdata-%(name)s" % {
                                'name': name,
                                'release': release
                           }
    run(create_container_cmd, quiet=False)
    return


def get_container_ip(name):
    """:name - return a container ip address given his name"""
    env_backup = (env.user, env.password)
    env.user, env.password = env.lxc.user_name, env.lxc.user_password
    ip = run("lxc-ls --fancy --fancy-format=ipv4,name | grep %s | cut -d' ' -f1" % name, quiet=True)
    (env.user, env.password) = env_backup
    return ip.stdout


@task
def republish_ports():
    """Republish ports defined in .cfg file lxc.published_ports section"""
    for publication in LXCConfig.published_ports_list:
        publish_port(publication[0], publication[1], publication[2])


@task
def publish_port(name, private_port, public_port):
    """:name,private_port,public_port - setup a Port Translation of {{private port}} of container identified by {{name}} to {{public_port}."""
    env.user, env.password = env.root_user, env.root_password

    # TODO: check wether a port is available
    published = get_published_ports()
    is_published = filter(lambda item: item[1] == public_port, published)
    if is_published:
        print colors.red("ERROR: Public port '%s' is already used by container '%s' (%s)" % (is_published[0][1], get_container_for_ip(is_published[0][2]), is_published[0][2],))
        sys.exit(1)

    container_ip = get_container_ip(name)
    if not container_ip:
        print colors.red("ERROR: Container '%s' is not started or does not exists." % name)
        sys.exit(1)
    iptables_cmd = "iptables -t nat -A PREROUTING -i %(public_interface)s -p tcp " \
                   "--dport %(public_port)s -j DNAT " \
                   "--to %(container_ip)s:%(private_port)s" % \
                    {
                        'public_port': public_port,
                        'container_ip': container_ip,
                        'private_port': private_port,
                        'public_interface': env.lxc.public_interface,
                    }
    sudo(iptables_cmd)
    return


def get_published_ports():
    """retreive a list of all nat published ports."""
    env_backup = (env.user, env.password)
    env.user, env.password = env.root_user, env.root_password

    iptables_list_cmd = "iptables -n -t nat -L PREROUTING  --line-numbers"
    raw_list = sudo(iptables_list_cmd, quiet=True)
    raw_list_1 = raw_list.split('\r\n')[2:]
    raw_list_2 = [filter(None, sublist.split(' ')) for sublist in raw_list_1]
    raw_list_3 = [(rule[0], rule[-2][4:], rule[-1].split(':')[1], rule[-1].split(':')[2],) for rule in raw_list_2]

    env.user, env.password = env_backup
    return raw_list_3


@task
def unpublish_port(number):
    """:port - Unpublish port identified by rule {{number}}. Use lxc.list_published_ports to get rule numbers."""
    env_backup = (env.user, env.password)
    env.user, env.password = env.root_user, env.root_password

    cmd = "iptables -t nat -D PREROUTING %s" % number
    ret_value = sudo(cmd, quiet=False)

    env.user, env.password = env_backup
    return


@task
def list_published_ports(format_for='human'):
    """List all containers published ports."""
    env_backup = (env.user, env.password)

    env.user, env.password = env.root_user, env.root_password

    published_port_list = get_published_ports()
    container_list = get_container_list()

    if format_for == 'human':
        print "Number Public_port Container_IP    Container_name       Private_port"
        for entry in published_port_list:
            print "%6s %11s %-15s %-20s %12s" % (entry[0], entry[1], entry[2], get_container_for_ip(entry[2], container_list), entry[3])
    else:
        for entry in published_port_list:
            print "%s,%s,%s" % (get_container_for_ip(entry[2], container_list), entry[3], entry[1],)


    env.user, env.password = env_backup
    return


def get_container_list():
    """retreive the list of all containers."""
    env_backup = (env.user, env.password)
    env.user, env.password = env.lxc.user_name, env.lxc.user_password

    cmd = "lxc-ls --fancy"
    raw_list = run(cmd, quiet=True)
    raw_list_1 = raw_list.split('\r\n')[2:]
    raw_list_2 = [filter(None, sublist.split(' ')) for sublist in raw_list_1]

    env.user, env.password = env_backup
    return raw_list_2


def get_ip_for_container(name, container_list=None):
    """Return the ip of a container given his name."""
    container_list = container_list or get_container_list()
    ips = filter(lambda container: container[0] == name, container_list)
    return ips[0][2] if len(ips) else ''


def get_container_for_ip(ip, container_list=None):
    """Return the ip of a container given his name."""
    container_list = container_list or get_container_list()
    ips = filter(lambda container: container[2] == ip, container_list)
    return ips[0][0] if len(ips) else ''


@task
def ls():
    """List all '%s' container's with status and ip.""" % env.lxc.user_name
    env.user, env.password = env.lxc.user_name, env.lxc.user_password
    cmd = "lxc-ls --fancy"
    run(cmd)
    return


@task
def start(name):
    """:name - Start container idenfified by {{name}}."""
    env_backup = (env.user, env.password)
    env.user, env.password = env.lxc.user_name, env.lxc.user_password
    if not name:
        print colors.red("ERROR: container name is required.")
        sys.exit(1)

    cmd = "lxc-start -n %s -d" % name
    run(cmd)

    (env.user, env.password) = env_backup
    return


@task
def stop(name):
    """:name - Stop container idenfified by {{name}}."""
    env_backup = (env.user, env.password)
    env.user, env.password = env.lxc.user_name, env.lxc.user_password
    if not name:
        print colors.red("ERROR: container name is required.")
        sys.exit(1)

    cmd = "lxc-stop -n %s" % name
    run(cmd)
    (env.user, env.password) = env_backup
    return


def get_rules_for_container(name):
    container_ip = get_ip_for_container(name)
    published_ports = get_published_ports()
    rules = filter(lambda rule: rule[2] == container_ip, published_ports)
    return rules


@task
def destroy(name):
    """:name - Destroy container idenfified by {{name}} and unpublished all his ports. If container is running ports will be automatically published."""
    env.user, env.password = env.lxc.user_name, env.lxc.user_password
    if not name:
        print colors.red("ERROR: container name is required.")
        sys.exit(1)

    rules = get_rules_for_container(name)
    while rules:
        unpublish_port(rules[0][0])
        rules = get_rules_for_container(name)

    cmd = "lxc-stop -n %s" % name
    run(cmd, quiet=False, warn_only=True)

    cmd = "lxc-destroy -n %s" % name
    run(cmd, quiet=False, warn_only=True)
    return



