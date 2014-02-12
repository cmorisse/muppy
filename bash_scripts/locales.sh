# Probleme:
# La restoration d'une base francaise ou belge plante à cause d'un problème de locale
# non présente sur le serveur cible.
# 
# Solution:
#   Installer les locales cible
#   Reconstruire le cluster postgresql
# Install missing locale
sudo locale-gen fr_FR
sudo locale-gen fr_FR.utf8
sudo update-locale

# check locale are installed
locale -a

# rebuild postgres cluster
sudo pg_dropcluster --stop 9.1 main
sudo pg_createcluster --start --locale=fr_FR.UTF-8 9.1 main