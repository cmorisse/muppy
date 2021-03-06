.. _deploy_with_supervisor:

Deploy with supervisor
######################

Supervisor deployment with muppy is designed this way:

- Supervisor deployment is activated by a ``supervisor`` directive in muppy config file
- Muppy installs the Linux distribution's provided supervisor
- The appserver buildout is setup to generate a supervisor.conf file which contains only the ``[program:...]`` sections.
- Muppy passes generated .conf file to system supervisor by symlinking generated file in the included configuration folder (eg. /etc/supervisor/conf.d on Ubuntu)
- Muppy openerp.start and stop rely on supervisor

Activate Supervisor deployment
------------------------------

In the muppy config file, add a




Setup the appserver to generate a supervisor config file
--------------------------------------------------------

In the Odoo appserver buildout.cfg, apply these changes:

- Add a supervisor section in buildout.cfg
- Specify the version of the required supervisor recipe
- Add a ``supervisor`` entry in buildout parts directive


Add a supervisor section
````````````````````````

Here is a commented example of a valid [supervisor] section.

.. code-block:: ini

    [supervisor]
    recipe = collective.recipe.supervisor
    #
    # We only want to generate the programs section so that we can symlink generated file
    # to /etc/supervisor/conf.d/
    sections = services

    #
    # Following options are ignored due to sections settings above
    #http-socket = unix
    #file = ${buildout:directory}/var/supervisord.sock
    # port = 127.0.0.1:9001
    #supervisord-conf = ${buildout:directory}/etc/supervisord.conf
    #logfile = ${buildout:directory}/var/log/supervisord.log
    #pidfile = ${buildout:directory}/var/supervisord.pid
    #loglevel = info

    #
    # vars used to configure programs
    logfile_openerp = ${buildout:directory}/var/log/openerp-stdout.log

    # User owner of preocesses (supervisor default is to run as root which is impossible for odoo)
    process_owner_user = admodoo

    # number of workers for multi process programs
    openerp_workers = 4

    #
    # openerp connector specifics
    logfile_openerp_connector = ${buildout:directory}/var/log/openerp-connector-stdout.log
    # number of connecto worker processes
    connector_workers = 2

    # Note: Last one is for
    programs =
        10 odoo_mono_mt (autostart=false) "${buildout:directory}/bin/start_openerp" [ --logfile "${:logfile_openerp}" --workers=0 ] ${buildout:directory} true ${:process_owner_user}
        10 odoo_multi_mt "${buildout:directory}/bin/start_openerp" [ --logfile "${:logfile_openerp}" --workers=${:openerp_workers}] ${buildout:directory} true ${:process_owner_user}
        10 odoo_worker_mt "${buildout:directory}/bin/python_openerp" [ "${buildout:directory}/parts/connector/openerp-connector/connector/openerp-connector-worker" --config="${buildout:directory}/etc/openerp.cfg"  --logfile "${:logfile_openerp_connector}" --workers=${:connector_workers}] ${buildout:directory} true ${:process_owner_user}


Specify the version of the supervisor recipe
````````````````````````````````````````````

Muppy depends on the version **0.20.dev0** of the collective.recipe.supervisor which is not available
yet on Pypi. So we will install the recipe directly from github.
For that we need to:

- add a find-links directives that points on github
- specify the version in the buildout.cfg

Add a find-links directives that points on github
'''''''''''''''''''''''''''''''''''''''''''''''''

.. code-block:: ini

    find-links = http://github.com/collective/collective.recipe.supervisor/tarball/master#egg=collective.recipe.supervisor-0.20.dev0

Take a look at the syntax. In #egg=collective.recipe.supervisor-0.20.dev0 the egg name is after the ``#`` and
the version is after the ``-``.

Specify the version in the buildout.cfg
'''''''''''''''''''''''''''''''''''''''

Simply adda line in the ``[versions]`` section

.. code-block:: ini

    find-links = http://github.com/collective/collective.recipe.supervisor/tarball/master#egg=collective.recipe.supervisor-0.20.dev0

Take a look at the syntax. In #egg=collective.recipe.supervisor-0.20.dev0 the egg name is after the # and
the version is after the -


Add a ``supervisor`` entry in buildout parts directive
``````````````````````````````````````````````````````

Don't forget to reference your ``[supervisor]`` section in the ``parts`` directive of the ``[buildout]`` section as shown below.

.. code-block:: ini

    parts = openerp supervisor
    versions = versions
    ...


Troubles checklist
------------------

- Appserver generated supervisor config file must be:
  - named 'supervisord.conf'
  - located in {{appserver_root}}/parts/supervisor/supervisord.conf
