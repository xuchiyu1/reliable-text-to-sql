#!/bin/sh
# Runs once, when the mysql volume is empty, after the Sakila schema and data are loaded:
# create the read-only user for the second database (safety layer 3, same idea as init_reader.sh)
set -e
mysql --protocol=socket -uroot -p"$MYSQL_ROOT_PASSWORD" <<SQL
CREATE USER 'text2sql_reader'@'%' IDENTIFIED BY '$MYSQL_READER_PASSWORD';
GRANT SELECT ON sakila.* TO 'text2sql_reader'@'%';
SQL
