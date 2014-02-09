#
# Magento Installation Script
# Copyright (c) 2014 Cyril MORISSE ( @cmorisse )
#

# prerequisites
#sudo apt-get update --fix-missing &&  sudo apt-get upgrade -y && sudo apt-get install -y vim && sudo reboot

#
# Install parameter
#
# Apache hostname if Apache cannot resolve it
export APACHE_SERVER_NAME=magento

export MAGENTO_NAME=wwwmathoncom
export MAGENTO_FQDN="${MAGENTO_NAME}.inouk.io"
export MAGENTO_PORT=":8080"
export MAGENTO_URL="http://${MAGENTO_FQDN}${MAGENTO_PORT}"

export MAGENTO_DATABASE=$MAGENTO_NAME
export MAGENTO_ADMIN_USER=admin
export MAGENTO_ADMIN_PASSWORD=Effect12
export MAGENTO_ADMIN_FRONTNAME=trubino
export MAGENTO_ADMIN_EMAIL=cmorisse+mageadmin@boxes3.net

export MYSQL_HOST=localhost
export MYSQL_ROOT_PASSWORD=Effect12
export MYSQL_USER=mathon
export MYSQL_PASSWORD=Effect12

export MAGENTO_PACKAGE_NAME=Magento-Enterprise-Edition-v-1.13.1.0.gz
export MAGENTO_PACKAGE_URL="https://www.dropbox.com/s/4bhynsn4wnvmgcn/${MAGENTO_PACKAGE_NAME}"
#export MAGENTO_PACKAGE_NAME=magento-1.7.0.2.tar.gz
#export MAGENTO_PACKAGE_URL="http://www.magentocommerce.com/downloads/assets/1.7.0.2/${MAGENTO_PACKAGE_NAME}"

export MAGENTO_ROOT=/opt/magento/${MAGENTO_NAME}/magento

#
# Installation
#
sudo apt-get install -y apache2
sudo bash -c "echo \"ServerName ${APACHE_SERVER_NAME}\" >> /etc/apache2/conf.d/servername.conf"
sudo a2enmod rewrite
sudo service apache2 restart

# mysql var is password 
sudo debconf-set-selections <<< "mysql-server mysql-server/root_password password ${MYSQL_ROOT_PASSWORD}"
sudo debconf-set-selections <<< "mysql-server mysql-server/root_password_again password ${MYSQL_ROOT_PASSWORD}"
sudo apt-get install -y mysql-server

sudo mysql -hlocalhost -uroot -p$MYSQL_ROOT_PASSWORD -e "CREATE DATABASE ${MAGENTO_DATABASE}; INSERT INTO mysql.user (User,Host,Password) VALUES('${MYSQL_USER}','localhost',PASSWORD('${MYSQL_PASSWORD}')); GRANT ALL PRIVILEGES ON ${MAGENTO_DATABASE}.* TO ${MYSQL_USER}; FLUSH PRIVILEGES;"



sudo apt-get install -y php5 php5-curl php5-gd php5-mcrypt php5-mysql

sudo mkdir -p /opt/magento
sudo chgrp www-data /opt/magento
sudo chmod 2755 /opt/magento
sudo mkdir -p /opt/magento/$MAGENTO_NAME
sudo mkdir -p /opt/magento/$MAGENTO_NAME/log

sudo wget $MAGENTO_PACKAGE_URL -O /opt/magento/$MAGENTO_PACKAGE_NAME
sudo tar -xzvf /opt/magento/$MAGENTO_PACKAGE_NAME -C /opt/magento/$MAGENTO_NAME
# sudo rm /opt/magento/magento-1.7.0.2.tar.gz

sudo chmod -R g+w /opt/magento/$MAGENTO_NAME/magento/app/etc
sudo chmod -R g+w /opt/magento/$MAGENTO_NAME/magento/media

sudo bash -c "echo \"<VirtualHost *:80>
  ServerName  ${MAGENTO_URL}
  # ServerAlias ${MAGENTO_NAME}
  DocumentRoot /opt/magento/${MAGENTO_NAME}/magento
  LogLevel warn
  ErrorLog  /opt/magento/${MAGENTO_NAME}/log/error.log
  CustomLog /opt/magento/${MAGENTO_NAME}/log/access.log combined
</VirtualHost>\" > /etc/apache2/sites-available/${MAGENTO_FQDN}"

sudo a2ensite $MAGENTO_FQDN
sudo service apache2 restart

#
# Magento Installation
#
sudo bash -c "php -f /opt/magento/${MAGENTO_NAME}/magento/install.php -- \
  --license_agreement_accepted yes \
  --locale \"fr_FR\" \
  --timezone \"Europe/Paris\" \
  --default_currency \"EUR\" \
  --db_host \"${MYSQL_HOST}\" \
  --db_name \"${MAGENTO_DATABASE}\" \
  --db_user \"${MYSQL_USER}\" \
  --db_pass \"${MYSQL_PASSWORD}\" \
  --url \"${MAGENTO_URL}\" \
  --skip_url_validation  \
  --use_rewrites yes \
  --admin_frontname \"${MAGENTO_ADMIN_FRONTNAME}\" \
  --use_secure_admin no \
  --admin_firstname \"Admin\" \
  --admin_lastname \"ISTRATOR\" \
  --admin_email \"${MAGENTO_ADMIN_EMAIL}\" \
  --admin_username \"${MAGENTO_ADMIN_USER}\" \
  --admin_password \"${MAGENTO_ADMIN_PASSWORD}\" \
  --use_secure no \
  --secure_base_url \"\""



#
# Magento OpenERP OpenLABS Connector
#
sudo apt-get install -y bzr
sudo bzr branch lp:magentoerpconnect/magento-module-oerp6.x-stable /opt/magento/magento-module
sudo chgrp -R www-data /opt/magento/magento-module
sudo ln -fs /opt/magento/magento-module/Openlabs_OpenERPConnector-1.1.0/ $MAGENTO_ROOT/app/code/community/Openlabs_OpenERPConnector-1.1.0
sudo chgrp -Rh www-data $MAGENTO_ROOT/app/code/community/Openlabs_OpenERPConnector-1.1.0/

sudo ln -fs /opt/magento/magento-module/Openlabs_OpenERPConnector-1.1.0/app/etc/modules/Openlabs_OpenERPConnector.xml $MAGENTO_ROOT/app/etc/modules
sudo chgrp -Rh www-data $MAGENTO_ROOT/app/etc/modules/Openlabs_OpenERPConnector.xml
sudo reboot



