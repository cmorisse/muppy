#!/bin/bash 

#
# PostgreSQL Cloud Backup 
# Copyright (c) 2013, 2014 Cyril MORISSE ( @cmorisse )
# Licence AGPL 3.0
# 
# This script:
#  - backs up all postgresql databases reacbable by provided user.
#
# If your crontab sucks (as mine often does), add a MAILTO=me@domain.com so that crontab mail you the log ...
#
# 
BACKUP_ROOT=_@@backup_root_directory
BACKUP_PATH=_@@backup_files_directory
EMAIL_RECIPIENTS='_@@backup_email_recipients'
BACKUP_LOG_FILENAME=`date +%Y%m%d_%H%M%S`__postgresql_backup__`hostname`.log
BACKUP_RETENTION_PERIOD_ON_LOCAL_SERVER=_@@backup_retention_period_in_days
PGUSER='_@@pg_user'
PGPASSWORD='_@@pg_password'
USE_DROPBOX=_@@activate_dropbox_integration


# 
# retrieve db list
#
DATABASE_LIST=`export PGPASSWORD=$PGPASSWORD && psql -h localhost -U $PGUSER --no-align --pset footer -t -c "SELECT datname FROM pg_database WHERE datistemplate = FALSE ;" postgres`

IFS=$'\n'  # !! must be single quoted 
DB_NAME_ARRAY=($DATABASE_LIST)

# Due to a lack of memory muscle...
# python vs bash array syntax
# echo "db[0]="${DB_NAME_ARRAY[0]}
# echo "db[3]="${DB_NAME_ARRAY[3]}
# echo "len(DB_NAME_ARRAY)="${#DB_NAME_ARRAY[@]}

#
# Generate backup log file header
#
echo "Server             : `hostname`" > ${BACKUP_PATH}/${BACKUP_LOG_FILENAME}
echo "Date               : `date`" >> ${BACKUP_PATH}/${BACKUP_LOG_FILENAME}
echo "Database backed up : ${#DB_NAME_ARRAY[@]}" >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
echo >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
echo >> $BACKUP_PATH/$BACKUP_LOG_FILENAME

#
# backup loop
#
for DATABASE_NAME in ${DB_NAME_ARRAY[@]}
do
	# Proceed with dump
	BACKUP_FILENAME=`date +%Y%m%d_%H%M%S`__${DATABASE_NAME}__`hostname`.pg_dump
	LATEST_FILENAME=latest_postgresql_backup_db__${DATABASE_NAME}__`hostname`.pg_dump
	export PGPASSWORD=$PGPASSWORD && pg_dump -h localhost -U $PGUSER -Fc -f$BACKUP_PATH/$BACKUP_FILENAME $DATABASE_NAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
	cp $BACKUP_PATH/$BACKUP_FILENAME $BACKUP_PATH/$LATEST_FILENAME

	echo "Backup file      = $BACKUP_FILENAME" >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
	BACKUP_FILE_SIZE=`du $BACKUP_PATH/$BACKUP_FILENAME | sed 's:\t/.*pg_dump::'`
	echo "Backup file size = $BACKUP_FILE_SIZE Ko" >> $BACKUP_PATH/$BACKUP_LOG_FILENAME

	if [[ $USE_DROPBOX == True ]] ; then
		# upload to dropbox using git://github.com/andreafabrizi/Dropbox-Uploader.git
		# Since the App is configured with restricted access, we don't upload in a specific folder. That's Dropbox job.
		$BACKUP_ROOT/scripts/dropbox_uploader.sh upload $BACKUP_PATH/$BACKUP_FILENAME $BACKUP_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
		$BACKUP_ROOT/scripts/dropbox_uploader.sh upload $BACKUP_PATH/$LATEST_FILENAME $LATEST_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
	fi

	echo >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
done

#
# email backup log 
# 
IFS=$','
EMAIL_RECIPIENTS_ARRAY=($EMAIL_RECIPIENTS)
for EMAIL in ${EMAIL_RECIPIENTS_ARRAY[@]}
do
	mail -s "`hostname` PostgreSQL daily backup summary" $EMAIL < $BACKUP_PATH/$BACKUP_LOG_FILENAME
done

#
# locally, we keep only backups for the retention period parameter
#
if [[ -n $BACKUP_RETENTION_PERIOD_ON_LOCAL_SERVER ]] ; then
    find $BACKUP_PATH -type f -name "*pg_dump" -mtime +$BACKUP_RETENTION_PERIOD_ON_LOCAL_SERVER -exec rm -f {} \;
    find $BACKUP_PATH -type f -name "*log" -mtime +$BACKUP_RETENTION_PERIOD_ON_LOCAL_SERVER -exec rm -f {} \;
fi
