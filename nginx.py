from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists, append, upload_template
from fabric.colors import *
import sys
import string

from system import get_system_version

"""
Nginx related tasks
"""

TEMPLATE_CFG_SECTION = """

[nginx]
#
# Nginx configuration.
# Muppy is able to configure Nginx for both http and https. 
# 2 nginx configuration templates are used (one for http 
# and one for https).
#
# server_dns_name: *Required* 
#    Server's public dns name
server_dns_name={{server_fqdn:gandalf.lor.net}}

#
# odoo_backend_url: *Optional*
#    URL of odoo process that will receive regular requests
#odoo_backend_url=http://127.0.0.1:8069

#
# odoo_backend_long_polling_url: *Optional*
#    URL of odoo process that will long polling/chat requests
#odoo_backend_long_polling_url=http://127.0.0.1:8072


#
# HTTPS
# 
# Important
# =========
#    Before activating https, you must ensure you have these lines in your security setup:
#allow_rules = tcp any any https # everybody can connect to odoo with https
#              tcp any any 8072  # allow chat use (optional but recommended)
#              tcp any any http  # everybody can connect to odoo with http (optional)
#

#
# activate_lets_encrypt: *Optional*
#    if True will install let's encrypt, use it to generate a 
#    certificate and configure nginx to use it.
#activate_lets_encrypt=False

#
# lets_encrypt_owner_email: *required* to activate let's encrypt
#lets_encrypt_owner_email=owner@domain.ext

#
# Advanced
# ========
# config_file_template:optional
#     Allows to use an alternative custom nginx config template file
#config_file_template=nginx-odoo.conf.template
"""


class NginxConfig:
    pass


def parse_config(config_parser):
    if not config_parser.has_section('nginx'):
        return None
    
    if not config_parser.has_option('nginx', 'server_dns_name'):
        print colors.red("'server_dns_name' config is required in [nginx] section !!")
        sys.exit(1)

    server_dns_name = config_parser.get('nginx', 'server_dns_name')
    if len(server_dns_name.split('.')) < 2:
        print colors.red("'server_dns_name' must be a valide dns name built as domain.ext or srv.domain.ext or srv.subdom.domain.ext !!")
        sys.exit(1)
    NginxConfig.server_dns_name = server_dns_name
    
    NginxConfig.odoo_backend_url = (
            config_parser.has_option('nginx', 'odoo_backend_url') 
        and config_parser.get('nginx', 'odoo_backend_url')
    ) or 'http://127.0.0.1:8069'

    NginxConfig.odoo_backend_long_polling_url = (
            config_parser.has_option('nginx', 'odoo_backend_long_polling_url') 
        and config_parser.get('nginx', 'odoo_backend_long_polling_url')
    ) or 'http://127.0.0.1:8072'

    NginxConfig.activate_lets_encrypt = (
            config_parser.has_option('nginx', 'activate_lets_encrypt') 
        and eval(config_parser.get('nginx', 'activate_lets_encrypt'))
    ) or False
    
    if NginxConfig.activate_lets_encrypt:
        if not config_parser.has_option('nginx', 'lets_encrypt_owner_email'):
            print colors.red("'lets_encrypt_owner_email' config is required in [nginx] section if let's encrypt is activated!!")
            sys.exit(1)
        
        NginxConfig.lets_encrypt_owner_email = config_parser.get('nginx', 'lets_encrypt_owner_email')

    NginxConfig.config_file_template = (
            config_parser.has_option('nginx', 'config_file_template') 
        and config_parser.get('nginx', 'config_file_template')
    ) or 'nginx-odoo.conf.template'
    
    return NginxConfig


def install_lets_encrypt():
    """Internal let's encrypt installer"""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    sudo('add-apt-repository -y ppa:certbot/certbot')
    sudo('apt install -y python-certbot-nginx')
    env.user, env.password = env_backup
    return 


@task
def install():
    """Install nginx"""
    # 'psql -h localhost -U openerp --no-align --pset footer -t -c "SELECT datname FROM pg_database WHERE datistemplate = FALSE ;" postgres'
    env_backup = (env.user, env.password,)
    env.user, env.password = env.root_user, env.root_password

    sudo('apt-get install -y nginx')
    
    if env.nginx.activate_lets_encrypt:
         install_lets_encrypt()

    reconfigure()
    
    env.user, env.password = env_backup
    return 

@task
def reconfigure():
    """Regenerate nginx config file and restart nginx"""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    template_context = {
        "activate_lets_encrypt": env.nginx.activate_lets_encrypt,
        "server_dns_name": env.nginx.server_dns_name,
        "odoo_backend_url": env.nginx.odoo_backend_url,
        "odoo_backend_long_polling_url": env.nginx.odoo_backend_long_polling_url,
    }

    config_filename = "odoo_appserver_%s_http.conf" % env.appserver_id
    upload_template('./templates/%s' % env.nginx.config_file_template,
                    "/etc/nginx/sites-available/%s" % config_filename, 
                    context=template_context,
                    use_jinja=True,
                    template_dir=None, 
                    use_sudo=True, 
                    backup=False, 
                    mirror_local_mode=False, 
                    mode=None, 
                    pty=None)
                    #keep_trailing_newline=False, 
                    #temp_dir='')
    print cyan("Nginx config file: %s uploaded." % ("/etc/nginx/sites-available/%s" % config_filename,))
    
    sudo('rm -rf /etc/nginx/sites-enabled/default')
    sudo('rm -rf /etc/nginx/sites-enabled/%s' % config_filename)
    sudo('ln -s /etc/nginx/sites-available/%s /etc/nginx/sites-enabled/' % config_filename)
    print cyan("Nginx config file: %s uploaded." % ("/etc/nginx/sites-enabled/%s" % config_filename,))

    # reconfigure let's encrypt
    if env.nginx.activate_lets_encrypt:
        sudo('certbot --nginx --agree-tos --email=%s -n -d %s'% (env.nginx.lets_encrypt_owner_email, env.nginx.server_dns_name,))
    

    sudo('systemctl restart nginx.service')
    print cyan("Nginx restarted")

    env.user, env.password = env_backup
    return



@task
def generate_config_template():
    """Generate a template [nginx] section that you can copy paste into muppy config file."""
    print TEMPLATE_CFG_SECTION

