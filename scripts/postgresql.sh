# Various snippets for postgresql


# Installation from postgresql
# Reference: https://askubuntu.com/questions/831292/how-to-install-postgresql-9-6-on-any-ubuntu-version

# On ubuntu 16.04
sudo add-apt-repository "deb http://apt.postgresql.org/pub/repos/apt/ xenial-pgdg main"
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get install postgresql-9.6

# Re install a cluster with a different locale
# https://makandracards.com/makandra/18643-how-the-change-the-locale-of-a-postgresql-cluster

pg_dropcluster --stop 9.2 main
pg_createcluster --locale en_US.UTF-8 --start 9.2 main

# But the new locale must exists


# On Ubuntu 14.04

sudo add-apt-repository "deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main"
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get install postgresql-9.6

# Pour virer ancien cluster et créer un 9.6 comme cluster par defaut
sudo pg_dropcluster --stop 9.3 main 
sudo pg_dropcluster --stop 9.6 main 
sudo pg_createcluster --locale fr_FR.UTF-8 --start 9.6 main
