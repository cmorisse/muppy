cp /opt/openerp/sido/appserver-sido/buildout.cfg.template /opt/openerp/sido/appserver-sido/buildout.cfg
sed -i.bak -r -e 's/\{\{pg_user\}\}/openerp/g' /opt/openerp/sido/appserver-sido/buildout.cfg
sed -i.bak -r -e 's/\{\{pg_password\}\}/2Z1yiHS8Pw/g' /opt/openerp/sido/appserver-sido/buildout.cfg
sed -i.bak -r -e 's/\{\{openerp_admin_password\}\}/D!w@l&ght09/g' /opt/openerp/sido/appserver-sido/buildout.cfg


##################################################################################################################
start-stop-daemon --start --quiet --pidfile /var/run/openerp/openerp-server.pid --chuid admsido \
--background --make-pidfile \
--exec /opt/openerp/sido/appserver-sido/bin/start_openerp \
-- --logfile=/var/log/openerp/openerp-server.log --log-handler=:ERROR

start-stop-daemon --start --pidfile /var/run/openerp/openerp-server.pid --chuid admsido \
--background --make-pidfile --exec /opt/openerp/sido/appserver-sido/bin/start_openerp 


start-stop-daemon --stop --pidfile /var/run/openerp/openerp-server.pid 
