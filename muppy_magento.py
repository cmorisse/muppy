from urlparse import urlparse
from fabric.api import *
from fabric.contrib.files import exists
from fabric.colors import *
import sys
"""
Magento is installed using a sudoer account.
Installed website is run by apache with the 'www-data' user.
"""

# TODO: we should be able provide host information in magento section and default to env.host if none is provied in magento section

class _MagentoConfig:
    pass

def _magento_parse_config(config_parser):
    if config_parser.get('magento', 'install_magento') and eval(config_parser.get('magento', 'install_magento')):
      _MagentoConfig.apache_server_name = config_parser.get('magento', 'apache_server_name')
      up = urlparse(config_parser.get('magento', 'url'))
      if up.scheme != 'http':
          print red("Error: Muppy is unable to install Magento secured (https) sites.")
          sys.exit(1)
      _MagentoConfig.url = up.geturl()
      _MagentoConfig.site_fqdn = up.netloc.split(':')[0] if up.port else up.netloc  # url without scheme and port
      _MagentoConfig.site_name = config_parser.get('magento', 'site_name')
      _MagentoConfig.site_port = up.port
      _MagentoConfig.enc_key = config_parser.get('magento', 'enc_key')

      _MagentoConfig.mysql_host = (config_parser.has_option('magento', 'mysql_host') \
                                   and config_parser.get('magento', 'mysql_host')) \
                                   or 'localhost'
      _MagentoConfig.mysql_root_password = config_parser.get('magento', 'mysql_root_password')
      _MagentoConfig.mysql_database_name = (config_parser.has_option('magento', 'mysql_database_name') \
                                            and config_parser.get('magento', 'mysql_database_name')) \
                                            or _MagentoConfig.site_name
      _MagentoConfig.mysql_user = config_parser.get('magento', 'mysql_user')
      _MagentoConfig.mysql_password = config_parser.get('magento', 'mysql_password')

      _MagentoConfig.admin_user = config_parser.get('magento', 'admin_user')
      _MagentoConfig.admin_password = config_parser.get('magento', 'admin_password')
      _MagentoConfig.admin_email = config_parser.get('magento', 'admin_email')
      _MagentoConfig.admin_frontname_url = config_parser.get('magento', 'admin_frontname_url')

      _MagentoConfig.MAGENTO_ROOT = (config_parser.has_option('magento', 'MAGENTO_ROOT') \
                                     and config_parser.get('magento', 'MAGENTO_ROOT')) \
                                     or "/opt/magento/%s/magento" % _MagentoConfig.site_name

      _MagentoConfig.MAGENTO_DOWNLOAD_URL = config_parser.get('magento', 'MAGENTO_DOWNLOAD_URL')
      _MagentoConfig.MAGENTO_FILE_NAME = _MagentoConfig.MAGENTO_DOWNLOAD_URL.split('/')[-1]

      _MagentoConfig.install_openlabs_connector = config_parser.get('magento', 'install_openlabs_connector')
      _MagentoConfig.create_api_user = config_parser.get('magento', 'create_api_user')
      _MagentoConfig.api_username = config_parser.get('magento', 'api_username')
      _MagentoConfig.api_user_email = config_parser.get('magento', 'api_user_email')
      _MagentoConfig.api_key = config_parser.get('magento', 'api_key')

      if _MagentoConfig.api_key and not _MagentoConfig.enc_key:
          print red("Error: missing enc_key.")
          print red("Error: enc_key is required as you defined an api_key.")
          sys.exit(1)

    return _MagentoConfig


def magento_install():
    """Magento initial installation"""
    env.user = env.root_user
    env.password = env.root_password

    sudo("apt-get install -y apache2")
    sudo("echo \"ServerName %s\" >> /etc/apache2/conf.d/servername.conf" % env.magento.apache_server_name)
    sudo("a2enmod rewrite")
    sudo("service apache2 restart")
    print green("Apache2 is installed")

    #
    # We add root_user and adm_user to www-data group
    #
    sudo("adduser %s www-data" % env.root_user)
    ret_val = sudo('getent passwd %s' % env.adm_user, warn_only=True, quiet=True)   
    if ret_val.succeeded: 
        sudo("adduser %s www-data" % env.adm_user)

    #
    # mysql
    #
    sudo("debconf-set-selections <<< \"mysql-server mysql-server/root_password password %s\"" % env.magento.mysql_root_password)
    sudo("debconf-set-selections <<< \"mysql-server mysql-server/root_password_again password %s\"" % env.magento.mysql_root_password)
    sudo("apt-get install -y mysql-server") 
    # we create the magento database and user
    command_line = "mysql -h%s -uroot -p%s -e \"CREATE DATABASE %s; INSERT INTO mysql.user (User,Host,Password) VALUES('%s','%s',PASSWORD('%s')); GRANT ALL PRIVILEGES ON %s.* TO %s; FLUSH PRIVILEGES;\"" % (env.magento.mysql_host, env.magento.mysql_root_password, env.magento.mysql_database_name, env.magento.mysql_user, env.magento.mysql_host, env.magento.mysql_password, env.magento.mysql_database_name, env.magento.mysql_user)
    sudo(command_line)
  
    #
    # Php 
    #
    sudo("apt-get install -y php5 php5-curl php5-gd php5-mcrypt php5-mysql")

    #
    # Setup magento directory 
    #    
    sudo("mkdir -p /opt/magento")
    sudo("chgrp www-data /opt/magento")
    sudo("chmod 2750 /opt/magento")
    sudo("mkdir -p /opt/magento/%s/log" % env.magento.site_name)

    #
    # Download, extract and set permissions on magento root folder
    #
    sudo("wget %s -O /opt/magento/%s" % (env.magento.MAGENTO_DOWNLOAD_URL, env.magento.MAGENTO_FILE_NAME,))
    sudo("tar -xzvf /opt/magento/%s -C /opt/magento/%s" % (env.magento.MAGENTO_FILE_NAME, env.magento.site_name))
    sudo("chmod -R g+w /opt/magento/%s/magento/app/etc" % env.magento.site_name)
    sudo("chmod -R g+w /opt/magento/%s/magento/media" % env.magento.site_name)

    #
    # Apache virtual host
    #
    command_line = """echo \"<VirtualHost *:80>
    ServerName  %s
    # ServerAlias %s
    DocumentRoot /opt/magento/%s/magento
    LogLevel warn
    ErrorLog  /opt/magento/%s/log/error.log
    CustomLog /opt/magento/%s/log/access.log combined
</VirtualHost>\" > /etc/apache2/sites-available/%s""" % (env.magento.site_fqdn, env.magento.site_name, 
                                                         env.magento.site_name, env.magento.site_name, 
                                                         env.magento.site_name, env.magento.site_fqdn)

    sudo(command_line)
    sudo("a2ensite %s" % env.magento.site_fqdn)
    sudo("service apache2 restart")

    #
    # Magento Installation
    #
    enc_key_param = "--encryption_key \"%s\"" % env.magento.enc_key if env.magento.enc_key else ''

    command_line = "php -f /opt/magento/%s/magento/install.php -- \
--license_agreement_accepted yes \
--locale \"fr_FR\" \
--timezone \"Europe/Paris\" \
--default_currency \"EUR\" \
--db_host \"%s\" \
--db_name \"%s\" \
--db_user \"%s\" \
--db_pass \"%s\" \
--url \"%s\" \
--skip_url_validation  \
--use_rewrites yes \
--admin_frontname \"%s\" \
--use_secure_admin no \
--admin_firstname \"Admin\" \
--admin_lastname \"ISTRATOR\" \
--admin_email \"%s\" \
--admin_username \"%s\" \
--admin_password \"%s\" \
--use_secure no \
--secure_base_url \"\" %s" % (env.magento.site_name, env.magento.mysql_host, 
                           env.magento.mysql_database_name, env.magento.mysql_user, 
                           env.magento.mysql_password, env.magento.url, 
                           env.magento.admin_frontname_url, env.magento.admin_email, 
                           env.magento.admin_user, env.magento.admin_password, 
                           enc_key_param,)
    sudo(command_line)
    print green("Magento installation finished.")
    
    if env.magento.install_openlabs_connector:
        magento_install_OpenLABS_Connector()

    if env.magento.create_api_user:
        magento_create_openerp_apiuser()

    print green("Rebooting...")
    reboot()

def magento_install_OpenLABS_Connector():
    """Install OpenLABS Magento OpenERP Connector"""
    env.user = env.root_user
    env.password = env.root_password

    print cyan("Installing OpenLABS Magento Connector")

    print cyan("apt-getting bzr")
    sudo("apt-get install -y bzr", quiet=True)
    if exists('/opt/magento/magento-module', use_sudo=True):
        sudo("rm -rf /opt/magento/magento-module")

    print cyan("bzr branch lp:magentoerpconnect/magento-module-oerp6.x-stable")
    sudo("bzr branch lp:magentoerpconnect/magento-module-oerp6.x-stable /opt/magento/magento-module")
    #sudo("chgrp -R www-data /opt/magento/magento-module")
    sudo("ln -fs /opt/magento/magento-module/Openlabs_OpenERPConnector-1.1.0/Openlabs %s/app/code/community/Openlabs" % env.magento.MAGENTO_ROOT)
    #sudo("chgrp -Rh www-data %s/app/code/community/Openlabs" % env.magento.MAGENTO_ROOT)

    sudo("ln -fs /opt/magento/magento-module/Openlabs_OpenERPConnector-1.1.0/app/etc/modules/Openlabs_OpenERPConnector.xml %s/app/etc/modules" % env.magento.MAGENTO_ROOT)
    sudo("chgrp -Rh www-data %s/app/etc/modules/Openlabs_OpenERPConnector.xml" % env.magento.MAGENTO_ROOT)
    print green("Openlabs_OpenERPConnector-1.1.0 installed. You must clear Magento cache.")

def magento_create_openerp_apiuser():
    """Install OpenLABS Magento OpenERP Connector params username, email, api_key"""
    env.user = env.root_user
    env.password = env.root_password

    # create the role
    command_line = "mysql -h%s -u%s -p%s -e\"INSERT INTO api_role " \
                   "(role_id, parent_id, tree_level, sort_order, role_type, user_id, role_name) " \
                   "VALUES (1, 0, 1, 0, 'G', 0, '%s_role');\"  %s" % (env.magento.mysql_host, 
                                                                      env.magento.mysql_user, 
                                                                      env.magento.mysql_password, 
                                                                      env.magento.api_username,
                                                                      env.magento.mysql_database_name,)
    sudo(command_line)

    # grant role access to "all"
    command_line = "mysql -h%s -u%s -p%s -e\"INSERT INTO api_rule " \
                   "(rule_id, role_id, resource_id, api_privileges, assert_id, role_type, api_permission ) " \
                   "VALUES (1, 1, 'all', NULL, 0, 'G', 'allow');\" %s" % (env.magento.mysql_host, 
                                                                          env.magento.mysql_user, 
                                                                          env.magento.mysql_password, 
                                                                          env.magento.mysql_database_name,)
    sudo(command_line)


    # create the user
    command_line = "mysql -h%s -u%s -p%s -e"\
                   "\"INSERT INTO api_user " \
                   "(user_id, firstname, lastname, email, username, api_key, is_active) " \
                   "VALUES (1, 'OpenERP', 'CONNECTOR', '%s', '%s', '%s', 1);\"  %s" % (env.magento.mysql_host, 
                                                                                       env.magento.mysql_user, 
                                                                                       env.magento.mysql_password, 
                                                                                       env.magento.api_user_email, 
                                                                                       env.magento.api_username, 
                                                                                       env.magento.api_key,
                                                                                       env.magento.mysql_database_name,)
    sudo(command_line)

    # bind the role to our user
    command_line = "mysql -h%s -u%s -p%s -e\"INSERT INTO api_role " \
                   "(role_id, parent_id, tree_level, sort_order, role_type, user_id, role_name) " \
                   "VALUES (2, 1, 1, 0, 'U', 1, 'OpenERP');\"  %s" % (env.magento.mysql_host, 
                                                                      env.magento.mysql_user, 
                                                                      env.magento.mysql_password, 
                                                                      env.magento.mysql_database_name,)
    sudo(command_line)
    print cyan("API user '%s' created." % env.magento.api_username)    
    return