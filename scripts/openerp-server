#!/bin/sh

### BEGIN INIT INFO
# Provides:             openerp-server
# Required-Start:       $remote_fs $syslog
# Required-Stop:        $remote_fs $syslog
# Should-Start:         $network
# Should-Stop:          $network
# Default-Start:        2 3 4 5
# Default-Stop:         0 1 6
# Short-Description:    Enterprise Resource Management software
# Description:          Open ERP is a complete ERP and CRM software.
### END INIT INFO

PATH=/bin:/sbin:/usr/bin
DAEMON={{muppy_appserver_path}}bin/start_openerp
NAME=openerp-server
DESC="Classical OpenERP launcher"

#
# Specify the user name who will own the process.
#USER=openerp
USER={{muppy_adm_user}}

# TODO: add pid number
PIDFILE=/var/run/$NAME.pid

#
# Additional options that are passed to the Daemon.
#
LOGFILE=/var/log/openerp/openerp-server.log
DAEMON_OPTS=" --logfile=$LOGFILE --log-handler=:ERROR"

[ -x $DAEMON ] || exit 0
[ -f $CONFIGFILE ] || exit 0

# TODO: Manage multi instance based on different network port
checkpid() {
    [ -f $PIDFILE ] || return 1
    pid=`cat $PIDFILE`
    [ -d /proc/$pid ] && return 0
    return 1
}

case "${1}" in
        start)
                echo -n "Starting \"${DESC}\": ... "
                start-stop-daemon --start --quiet --pidfile ${PIDFILE} --chuid ${USER} --background --make-pidfile  --exec ${DAEMON} -- ${DAEMON_OPTS}
                echo "${NAME} started."
                ;;

        stop)
                echo -n "Stopping \"${DESC}\": ... "
                start-stop-daemon --stop --quiet --pidfile ${PIDFILE} --oknodo
                echo "${NAME} stopped."
                ;;

        restart|force-reload)
                echo -n "Restarting \"${DESC}\": ... "
                start-stop-daemon --stop --quiet --pidfile ${PIDFILE} --oknodo
                sleep 1
                start-stop-daemon --start --quiet --pidfile ${PIDFILE} --chuid ${USER} --background --make-pidfile  --exec ${DAEMON} -- ${DAEMON_OPTS}
                echo "${NAME} restarted."
                ;;

        *)
                N=/etc/init.d/${NAME}
                echo "Usage: ${N} {start|stop|restart|force-reload}" >&2
                exit 1
                ;;
esac

exit 0

