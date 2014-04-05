from urlparse import urlparse
from fabric.api import *
from fabric.operations import *
from fabric.contrib.files import exists
from fabric.colors import *
from fabric import colors
import sys
import string

from muppy_utils import *
import postgresql
"""
OpenERP Application Server related tasks
"""


def get_running_service():
    backup = env.user, env.password
    env.user, env.password = env.root_user, env.root_password

    # identify wich server is running
    raw_server = sudo("ps -e -o %p,%c | grep [o]pener | cut -d',' -f2", quiet=True)
    if raw_server.failed:
        print red("ERROR: failed to ps")
        sys.exit(1)

    if raw_server:
        if raw_server.startswith('gunicorn'):
            running_service = 'gunicorn-openerp'
        else:
            running_service = 'openerp-server'
    else:
        running_service = None

    env.user, env.password = backup
    return running_service


@task
def stop_service():
    """Stop running OpenERP service wether it is running with gunicorn or classic OpenERP."""
    # This script has been designed to be really robust and accomodate buggy init scripts

    WAIT_TIME = 5  # Delay to wait after a kill or stop

    # We switch to root_user, but we preserve active user
    backup = env.user, env.password
    env.user, env.password = env.root_user, env.root_password

    running_service = get_running_service()

    if not running_service:
        print colors.magenta("WARNING: Did not find any running openerp service to stop !")
        return True
    print colors.blue("INFO: Running server is '%s'" % running_service)

    # we know which server is running, we can stop it
    print colors.blue("INFO: trying to use init.d script stop command.")
    if running_service == 'gunicorn-openerp':
        sudo('/etc/init.d/gunicorn-openerp stop', pty=False, quiet=True)
    else:
        sudo('/etc/init.d/openerp-server stop', pty=False, quiet=True)

    # we wait 3 seconds and check that are no openerp_process
    # if any we kill them
    time.sleep(WAIT_TIME)

    process_killed = 0
    iteration_num = 1  # the number of timer we try to kill a process
    result = None
    return_value = False
    while True:
        # We check there are no running openerp processes
        # Unix command is:
        #    ps -e -o %p,%c | grep [o]pener | cut -d',' -f1
        # Note that we search for opener (without the p) because
        # ps name field has length restriction
        raw_result = sudo("ps -e -o %p,%c | grep [o]pener | cut -d',' -f1", quiet=True)
        if raw_result.failed:
            print red("ERROR: failed to ps")
            sys.exit(1)
        # we filter sub processes
        if raw_result:
            last_result = result
            result = filter(lambda e: not (e is None or e.startswith(' ')), raw_result.split('\r\n'))[0]
        else:
            if process_killed == 0:
                print colors.green("OpenERP service '%s' stopped." % (running_service,))
            else:
                print colors.green("OpenERP service '%s' killed." % running_service)
            return_value = True
            break

        # stop failed, so we try to kill the same process up to 3 times
        if iteration_num < 4:
            # we kill identified process
            print colors.magenta("INFO: killing process %s" % result)
            sudo('kill -9 %s' % result, quiet=True)
            time.sleep(WAIT_TIME)
        else:
            print colors.red("ERROR: Unable to kill process '%s' (after %s attempts)." % (result, iteration_num,))
            print colors.red("ERROR: Unable to stop (kill) OpenERP service '%s'." % running_service)
            return_value = False
            break

        if result == last_result:
            iteration_num += 1
        else:
            process_killed += 1

    env.user, env.password = backup
    return return_value


@task
def start_service():
    """Start the OpenERP service setup to boot"""
    # We switch to root_user, but we preserve active usert
    backup = (env.user, env.password)

    env.user, env.password = env.root_user, env.root_password

    running_service = get_running_service()
    if not running_service:
        command_return = sudo("ls /etc/rc2.d/ | grep openerp-server", quiet=True, warn_only=True)
        if command_return.succeeded:
            print colors.blue("INFO: Currently active init.d script is 'openerp-server'")
            sudo('/etc/init.d/openerp-server start', pty=False, quiet=True)
            print green("OpenERP service 'openerp-server' started.")
        else:
            print colors.blue("INFO: Currently active init.d script is 'gunicorn-openerp'")
            sudo('/etc/init.d/gunicorn-openerp start', pty=False, quiet=True)
            print green("OpenERP service 'gunicorn-openerp' started.")
    else:
        print colors.magenta("WARNING: OpenERP '%s' service not started as it's already running." % running_service)

    env.user, env.password = backup
    return


@task
def buildout():
    """Launch a bin/buildout."""
    env.user = env.adm_user
    env.password = env.adm_password
    with cd(env.openerp.repository.path):
        run('bin/buildout')
    print colors.magento("WARNING: Check log above for errors !" % env.openerp.repository.path)
    print colors.green("Server '%s' buildout finished." % env.openerp.repository.path)

@task
def show_current_revision():
    """Display current revision of application server repository"""
    env.user = env.adm_user
    env.password = env.adm_password
    with cd(env.openerp.repository.path):
        run(env.openerp.repository.get_show_current_rev_command_line())

@task
def checkout_revision(refspec=None, launch_buildout='True'):
    """:commit[[,launch_buildout]] - Checkout openerp repository to given commit (or branch) and do a buildout depending on launch_buildout (default=True)."""
    env.user = env.adm_user
    env.password = env.adm_password
    #TODO: Test if refspec exists before
    #TODO: git show -s refspec => fatal: bad object badrefspec

    if not refspec:
        print red("ERROR: missing required refspec argument.")
        sys.exit(128)

    with cd(env.openerp.repository.path):
        run(env.openerp.repository.get_fetch_command_line())
        result = run(env.openerp.repository.get_checkout_command_line(refspec), warn_only=True)
    if result.failed:
        print red("ERROR: Failed to checkout repository '%s' to revision: '%s'." % (env.openerp.repository.path, refspec,))
        sys.exit(128)
    print green("Repository '%s' is now at revision '%s'." % (env.openerp.repository.path, refspec))

    if launch_buildout == 'True':
        buildout()


@task
def update_appserver(database=None, addons_list='all'):
    """:database[[,addons_list=all]] - Stop server, update OpenERP {{addons_list}} on {{database}} then restart the server."""
    env.user = env.adm_user
    env.password = env.adm_password

    if not database:
        print red("ERROR: missing required database parameter.")
        sys.exit(128)

    if database not in postgresql.get_databases_list(True):
        print red("ERROR: database '%s' does not exist on server." % database)
        sys.exit(128)

    stop_service()

    with cd(env.openerp.repository.path):
        run('bin/start_openerp -d %s -u %s --stop-after-init' % (database, addons_list))

    print green("Database '%s' updated for addon_list '%s'." % (database, addons_list,))

    start_service()


@task
def check_refspec(refspec, embedded=False):
    """:refspec - check if given refspec exists"""
    env_backup = (env.user, env.password,)
    env.user, env.password = env.adm_user, env.adm_password

    if not refspec:
        print red("ERROR: missing required refspec parameter.")
        sys.exit(128)

    if env.openerp.repository.dvcs != 'git':
        print colors.magenta("WARNING: check refspec not implemented with mercurial")
        return True
    with cd(env.openerp.repository.path):
        run('git fetch')
        result = run("git show -s %s" % refspec, quiet=True, warn_only=True)

    if not embedded:
        print result
    return result.succeeded


@task
def deploy_start(databases=None, new_refspec=None):
    """:"db_name1;db_name2",refspec - Deploy version designed by <<refspec>> param and update <<databases>>."""
    # if refspec is unspecifed will checkout latest version of branch master or default
    # if databases is unspecified, will update database designed by env.test_database_name.
    # NOTE: We do backup the postgres db but we don't restore it in case deploy file. You must
    #       restore by hand if needed

    env.user, env.password = env.adm_user, env.adm_password

    if not databases:
        print red("ERROR: missing required database list parameter.")
        sys.exit(128)

    if not new_refspec:
        print red("ERROR: missing required refspec parameter.")
        sys.exit(128)
    if not check_refspec(new_refspec, True):
        print red("ERROR: refspec %s does not exist in repo." % new_refspec)
        sys.exit(128)

    with cd(env.openerp.repository.path):
        old_refspec = run(env.openerp.repository.get_refspec_command_line(), quiet=True)
    print blue("Current refspec: %s" % old_refspec)

    # let's check that databases exist
    requested_database_list = databases and databases.split(';')

    existing_database_list = postgresql.get_databases_list(True)
    database_not_found = False
    print blue("Checking requested databases exist: "),
    if not requested_database_list:
        print magenta("skipped")
    else:
        print

    for requested_database in requested_database_list:
        if requested_database not in existing_database_list:
            database_not_found = True
            print red("  - %s : Error" % requested_database)
        else:
            print green("  - %s : Ok" % requested_database)
    if database_not_found:
        print red("deployment aborted.")
        exit(1)

    # We atomicaly generate a lock file or fail
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    hostname = get_hostname()
    database_dict = {requested_database: os.path.join(env.postgresql.backup_files_directory, "%s__%s__%s.pg_dump" % (timestamp, requested_database, hostname,)) for requested_database in requested_database_list}
    file_list = ",".join(database_dict.values())

    # open a log file
    log_file_name = "%s__%s__deploy.log" % (timestamp, hostname,)
    log_file = open(log_file_name, "w")
    print blue("INFO: Deploy log file is '%s'" % log_file_name)

    # generate lock file content
    lock_file_content = '[deploy]\nlog_file = %s\nold_refspec = %s\nnew_refspec = %s\ndatabases_to_update = %s' % (log_file_name, old_refspec, new_refspec, databases, )
    lock_file_path = os.path.join(env.muppy_transactions_directory, 'deploy.lock')
    create_lock = run('set -o noclobber && echo "%s" > %s' % (lock_file_content, lock_file_path,), quiet=True)
    if create_lock.failed:
        print red("ERROR: Unable to acquire %s" % lock_file_path)
        exit(1)

    # We have the lock, let's stop server and backup dbs
    stop_service()

    # backup the databases
    update_lock_file = run('echo "\n[databases_backups]" >> %s' % (lock_file_path,), quiet=True)
    if update_lock_file.failed:
        print red("ERROR: Unable to update lock file: '%s'" % lock_file_path)
        exit(1)

    postgresql.backup('postgres')  # we always backup postgres just in case
    for database_name, backup_file_name in database_dict.items():
        postgresql.backup(database_name, backup_file_name)
        lock_file_content = '%s = %s' % (database_name, backup_file_name,)
        update_lock_file = run('echo "%s" >> %s' % (lock_file_content, lock_file_path,), quiet=True)
        if update_lock_file.failed:
            print red("ERROR: Unable to update lock file: '%s' with '%s'" % (lock_file_path, lock_file_content,))
            exit(1)

    # checkout AND buildout
    checkout_revision(new_refspec)

    # openerp/update all modules on specified database(s)
    lock_file_content = "\n[update_database_statuses]"
    update_lock_file = run('echo "%s" >> %s' % (lock_file_content, lock_file_path,), quiet=True)
    if update_lock_file.failed:
        print red("ERROR: Unable to update lock file: '%s' with '%s'" % (lock_file_path, lock_file_content,))
        exit(1)

    error_during_update = False
    for database_name, backup_file_name in database_dict.items():
        if database_name == 'postgres':
            continue
        with cd(env.openerp.repository.path):
            print blue("INFO: Updating database '%s' for addons: '%s'." % (database_name, env.addons_list,))
            command_line = 'bin/start_openerp -d %s -u %s --stop-after-init' % (database_name, env.addons_list,)
            stdout = StringIO.StringIO()
            # bin/start_openerp --update always succeed. So we need to check stdout to find ERROR or Traceback
            retval = run(command_line, warn_only=True, stdout=stdout)
            error_log = stdout.getvalue()
            log_file.write(error_log)

            update_failed = 'ERROR' in error_log or 'Traceback' in error_log
            if update_failed:
                error_during_update = True
                lock_file_content = "%s = error" % database_name
                update_lock_file = run('echo "%s" >> %s' % (lock_file_content, lock_file_path,), quiet=True)
                if update_lock_file.failed:
                    print red("ERROR: Unable to update lock file: '%s' with '%s'" % (lock_file_path, lock_file_content,))
                    exit(1)
                print red("ERROR: Database '%s' update failed for addons='%s'. See detail in log '%s'." % (database_name, env.addons_list, log_file_name,))
            else:  # stderr is clean
                print green("INFO: Database '%s' update succeded for addons=%s. See detail in log '%s'." % (database_name, env.addons_list, log_file_name))

                lock_file_content = "%s = ok" % database_name
                update_lock_file = run('echo "%s" >> %s' % (lock_file_content, lock_file_path,), quiet=True)
                if update_lock_file.failed:
                    print red("ERROR: Unable to update lock file: '%s' with '%s'" % (lock_file_path, lock_file_content,))
                    exit(1)

    log_file.close()
    put(log_file_name, os.path.join(env.muppy_transactions_directory, log_file_name))

    if error_during_update:
        print red("ERROR: One or more update failed. OpenERP Server won't be restarted.")
        sys.exit(1)

    print green("Deploy ok ; restarting OpenERP server")
    start_service()
    sys.exit(0)


@task
def deploy_rollback(jobs=8):
    """[[jobs=8]] - Rollback a failed deploy (checkout repo to pre deploy commit and restore all updated databases using [[jobs]] cf. pg_restore doc)"""
    env.user = env.adm_user
    env.password = env.adm_password
    lock_file_path = os.path.join(env.muppy_transactions_directory, 'deploy.lock')

    if not exists(lock_file_path):
       print red("ERROR: Cannot Rollback ; lock file '%s' does not exists." % lock_file_path)
       exit(1)

    #
    # Reading lock file in a ConfigParser
    #
    lock_file_object = StringIO.StringIO()
    get(lock_file_path, lock_file_object)
    # Fabric returns a file object seeked at the end
    lock_file_object.seek(0)
    lock_file_parser = ConfigParser.ConfigParser()
    lock_file_parser.readfp(lock_file_object)

    stop_service()

    # We checkout the repo back to old_refspec
    refspec = lock_file_parser.get("deploy", "old_refspec")
    # checkout AND buildout
    checkout_revision(refspec)

    # we restore all databases with status = error
    databases_backups_dict = {db: lock_file_parser.get("databases_backups", db) for db in lock_file_parser.options("databases_backups")}
    update_database_statuses = {db: lock_file_parser.get("update_database_statuses", db) for db in lock_file_parser.options("update_database_statuses")}

    for db_name, db_status in update_database_statuses.items():
        backup_file = databases_backups_dict[db_name]
        if db_status == 'error':
            print colors.magenta("WARNING: Database '%s' update failed during deploy, restoring it using backup file '%s'" % (db_name, backup_file,))
            postgresql.restore(backup_file, jobs)
        elif db_status == 'ok':
            print colors.magenta("WARNING: Database '%s' update succeeded during deploy, restoring it using backup file '%s'" % (db_name, backup_file,))
            postgresql.restore(backup_file, jobs)

    start_service()

    # we archive lockfile
    lockfile_archive_name = lock_file_parser.get("deploy", "log_file").split('.')[0]+".archive.cfg"
    lockfile_archive_path = os.path.join(env.muppy_transactions_directory, lockfile_archive_name)
    print blue("INFO: Archiving deploy lock file to '%s'." % lockfile_archive_path)
    run('mv %s %s' % (lock_file_path, lockfile_archive_path,), quiet=True)

    print blue("INFO: Note that deploy_rollback leave backup files untouched.")
    print blue("INFO: deploy_rollback finished.")
    sys.exit(0)


@task
def deploy_commit():
    """Remove deploy.lock on server (archive it)."""
    env.user = env.adm_user
    env.password = env.adm_password
    lock_file_path = os.path.join(env.muppy_transactions_directory, 'deploy.lock')
    if not exists(lock_file_path):
        print red("ERROR: Cannot Commit ; lock file '%s' does not exists." % lock_file_path)
        sys.exit(1)

    #
    # Reading lock file in a ConfigParser
    #
    lock_file_object = StringIO.StringIO()
    get(lock_file_path, lock_file_object)
    # Fabric returns a file object seeked at the end
    lock_file_object.seek(0)
    lock_file_parser = ConfigParser.ConfigParser()
    lock_file_parser.readfp(lock_file_object)

    # we archive lockfile
    lockfile_archive_name = lock_file_parser.get("deploy", "log_file").split('.')[0]+".archive.cfg"
    lockfile_archive_path = os.path.join(env.muppy_transactions_directory, lockfile_archive_name)
    print blue("INFO: Archiving deploy lock file to '%s'." % lockfile_archive_path)
    run('mv %s %s' % (lock_file_path, lockfile_archive_path,), quiet=True)

    print magenta("INFO: Note that deploy_commit leave backups files untouched.")
    print blue("INFO: deploy_commit finished.")
    sys.exit(0)
