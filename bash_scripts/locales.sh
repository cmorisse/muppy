#!/bin/sh
# Probleme:
# La restoration d'une base francaise ou belge plante à cause d'un problème de locale
# non présente sur le serveur cible.
# 
# Solution:
#   Installer les locales cible
#   Reconstruire le cluster postgresql
# Install missing locale

export LANGUAGE="fr_FR"
export ENCODING="UTF-8"
sudo locale-gen "${LANGUAGE}.${ENCODING}"
sudo update-locale LANG="${LANGUAGE}.${ENCODING}" LANGUAGE="${LANGUAGE}" LC_ALL="${LANGUAGE}.${ENCODING}" LC_CTYPE="${LANGUAGE}.${ENCODING}"
sudo dpkg-reconfigure locales
logout #


# check locale are installed
locale -a

# rebuild postgres cluster
sudo pg_dropcluster --stop 9.1 main
sudo pg_createcluster --start --locale=fr_FR.UTF-8 9.1 main


#
# timezone
sudo dpkg-reconfigure tzdata

