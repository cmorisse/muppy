# Probleme:
# La restoration d'une base francaise ou belge plante à cause d'un problème de locale
# non présente sur le serveur cible.
# 
# Solution:
#   Installer les locales cible
#   Reconstruire le cluster postgresql
# Install missing locale

sudo locale-gen fr_FR.UTF-8
sudo update-locale LANG="fr_FR.UTF-8" LANGUAGE="fr_FR"
sudo dpkg-reconfigure locales

# check locale are installed
locale -a

# rebuild postgres cluster
sudo pg_dropcluster --stop 9.1 main
sudo pg_createcluster --start --locale=fr_FR.UTF-8 9.1 main


#
# timezone
sudo dpkg-reconfigure tzdata
