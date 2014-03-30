# Muppy

A set of python fabric functions to make your OpenERP 7 Servers behave as muppets !

Muppy is released with an MIT Licence.

Dont use muppy to install production servers. Muppy is intended only for Dev / tests servers.

## Installation

	hg clone ssh://hg@bitbucket.org/cmorisse/muppy
	cd muppy 
	./install.sh

## Config files
Create a config file for each server you want to manage.
Store them in the muppy/configs directory.

## Launch muppy
In the muppy directory, launch

	source py27/bin/activate
	fab --set config_file=configs/<<server.cfg>> 
	
With `<<server.cfg>>`is the name of your server config file.

#### Common muppy commands

#####--list

`fab --set config_file=configs/<<server.cfg>> --list`

List all availbale muppy commands.

##### mupping
`fab --set config_file=configs/<<server.cfg>> mupping`

Test a ls then sudo ls on remote server

##### update_appserver
`fab --set config_file=configs/<<server.cfg>> update_appserver:database=<<dbname>>`

This command:

* stop openerp server
* update the appserver repository (as well project_addons)
* buildout the serveyr
* restart it

## Muppy config files 
Muppy always use 2 system users:

 * **root_user**
 * **adm_user**

### root_user
root_user is a user with sudo privileges that Muppy will use for all system and configuration operations. Generally this is the system's root user created by your hosting provider.

### adm_user
adm_user is a system user created by muppy that will own and run openerp.

This user may be or not in the sudo group depending on the value of the _adm_user_is_sudoer_ parameter.

## How to work with https only repositories
The best is to create a dedicated user for each repository with readonly access.

In the muppy config file, include the user and password in the appserver_url like these examples:

* git https://username:password@bitbucket.org/owner/repository.git
* git https://username:password@github.com/owner/repository.git
* git https://username:password@yourgitlab.server.ext/owner/repository.git

Remember that:

* the username and password will be stored in clear in the remote url (See git remote -v).
So you must use a dedicated username and password with readonly access.
* You should use the same strategy to clone your addons using buildout cfg URLs. 


