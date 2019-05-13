#!/bin/bash 

# PostgreSQL Cloud Backup 
# Copyright (c) 2013-2018 Cyril MORISSE ( @cmorisse )
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
PG_HOST=_@@pg_host
PG_PORT=_@@pg_port
USE_DROPBOX=_@@activate_dropbox_integration
TARGET_SCP_SERVERS=_@@target_scp_servers
ODOO_DATA_DIR=_@@odoo_data_dir
USE_S3=_@@activate_s3_integration
S3_BUCKET_PREFIX=_@@s3_bucket_prefix
# 
# retrieve db list
#
DATABASE_LIST=`export PGPASSWORD=$PGPASSWORD && psql -h $PG_HOST -p $PG_PORT -U $PGUSER --no-align --pset pager=off --pset footer -t -c "SELECT datname FROM pg_database WHERE datistemplate = FALSE AND datname LIKE '_@@databases_prefix%';" postgres`

IFS=$'\n'  # !! must be single quoted 
DB_NAME_ARRAY=($DATABASE_LIST)
DB_NAME_ARRAY+=('postgres')  # always backup postgres db

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
	DATABASE_BACKUP_FILENAME=`date +%Y%m%d_%H%M%S`__${DATABASE_NAME}__`hostname`.pg_dump
	FILESTORE_BACKUP_FILENAME=`date +%Y%m%d_%H%M%S`__${DATABASE_NAME}__`hostname`.filestore.tgz
	LATEST_DATABASE_BACKUP_FILENAME=latest_postgresql_backup_db__${DATABASE_NAME}__`hostname`.pg_dump
	LATEST_FILESTORE_BACKUP_FILENAME=latest_odoo_filestore__${DATABASE_NAME}__`hostname`.filestore.tgz
	
	export PGPASSWORD=$PGPASSWORD && pg_dump -h $PG_HOST -p $PG_PORT -U $PGUSER -Fc -f$BACKUP_PATH/$DATABASE_BACKUP_FILENAME $DATABASE_NAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
    ln -sf $BACKUP_PATH/$DATABASE_BACKUP_FILENAME $BACKUP_PATH/$LATEST_DATABASE_BACKUP_FILENAME	
	if [ -d $ODOO_DATA_DIR/$DATABASE_NAME ] ; then
    	tar -czf $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME -C $ODOO_DATA_DIR $DATABASE_NAME
        ln -sf $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME $BACKUP_PATH/$LATEST_FILESTORE_BACKUP_FILENAME	
    fi

	echo "Backup file      = $DATABASE_BACKUP_FILENAME" >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
	BACKUP_FILE_SIZE=`du $BACKUP_PATH/$DATABASE_BACKUP_FILENAME | sed 's:\t/.*pg_dump::'`
	echo "Backup file size = $BACKUP_FILE_SIZE Ko" >> $BACKUP_PATH/$BACKUP_LOG_FILENAME

	if [ ! -z "$TARGET_SCP_SERVERS" ] ; then
		# Id defined copy backup file to scp_target_server.
		# Note that target server must have the same muppy backup folders hierarchy.
		IFS=$','
        for TARGET_SCP_SERVER in ${TARGET_SCP_SERVERS[@]}
        do
    		scp $BACKUP_PATH/$DATABASE_BACKUP_FILENAME $TARGET_SCP_SERVER:$BACKUP_PATH/$DATABASE_BACKUP_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
    		if [ -f $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME ] ; then
    			scp $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME $TARGET_SCP_SERVER:$BACKUP_PATH/$FILESTORE_BACKUP_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
    		fi
    		echo "Backup file copied to: $TARGET_SCP_SERVER" >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
    	done
	fi

	if [[ $USE_DROPBOX == True ]] ; then
		# upload to dropbox using git://github.com/andreafabrizi/Dropbox-Uploader.git
		# Since the App is configured with restricted access, we don't upload in a specific folder. That's Dropbox job.
		$BACKUP_ROOT/scripts/dropbox_uploader.sh upload $BACKUP_PATH/$DATABASE_BACKUP_FILENAME $DATABASE_BACKUP_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
		if [ -f $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME ] ; then
    		$BACKUP_ROOT/scripts/dropbox_uploader.sh upload $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME $FILESTORE_BACKUP_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
	    fi
	fi

	if [[ $USE_S3 == True ]] ; then
		# upload to S3 using AWS CLId
		$BACKUP_ROOT/scripts/py3x/bin/aws s3 cp $BACKUP_PATH/$DATABASE_BACKUP_FILENAME $S3_BUCKET_PREFIX/$DATABASE_BACKUP_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
		if [ -f $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME ] ; then
    		$BACKUP_ROOT/scripts/py3x/bin/aws s3 cp $BACKUP_PATH/$FILESTORE_BACKUP_FILENAME $S3_BUCKET_PREFIX/$FILESTORE_BACKUP_FILENAME >> $BACKUP_PATH/$BACKUP_LOG_FILENAME
	    fi
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
    find $BACKUP_PATH -type f -name "*.filestore.tgz" -mtime +$BACKUP_RETENTION_PERIOD_ON_LOCAL_SERVER -exec rm -f {} \;
    find $BACKUP_PATH -type f -name "*log" -mtime +$BACKUP_RETENTION_PERIOD_ON_LOCAL_SERVER -exec rm -f {} \;
fi
