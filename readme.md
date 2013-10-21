Muppy
=====

A set of python fabric functions to make your OpenERP 7 Servers behave as muppets !

Muppy is released with an MIT Licence.

Muppy is undocumented right now, but this is next on my todo list.

Users
-----
Muppy always use 2 system users:

 * **root_user**
 * **adm_user**

### root_user
root_user is a user with sudo privileges that Muppy will use for all system and configuration operations. Generally this is the system's root user created by your hosting provider.

### adm_user
adm_user is a system user created by muppy that will own and run openerp.

This user may be or not in the sudo group depending on the value of the _adm_user_is_sudoer_ parameter.


Roadmap
-------

* Document 
* Add SSH 2 step Authentication with Google Authenticators
* Repackage as an idendendant comman line utility
