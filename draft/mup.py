# -*- coding: utf-8 -*-
"""
Manages VMs as if they were puppets.
"""
from subprocess import call
import sys
import argparse
import logging
from os import execlp


_logger = logging.getLogger('muppy')
_logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s'))
_logger.addHandler(console_handler)



# TODO: Tout reprendre avec argparse

__version__ = '1.0'
__description__ = "muppy is a tool to manipulate VM as if they were puppets."
__program__ = "muppy"


def init():
    """
    Sets up a mupid card
    :return:
    :rtype:
    """
    pass


def up(args):
    """
    Starts a VM using:
    VBoxManage startvm <uuid>|<name> [--type gui|headless]

    :return:
    :rtype:
    """
    _logger.debug("in up()")
    _logger.debug("  args=%s" % args)

    option_type = 'gui' if args.gui else 'headless'

    if not args.vm_name:
        # We must launch default VM. VM Name is provided only when there is a muppy cluster in
        # current directory
        # TODO: How to retreive her name.
        print "call(['VBoxManage', 'startvm', vm_name, '--type', option_type)"
        # Quelle est le meilleur non
        # besoin pour ssh
        # besoin pour bitcket
        # besoin d'un nom unique
    return


def ssh(args):
    """
    Connect to a VM using SSH.
    """
    # TODO: how to retrieve address (from name ?)
    # TODO: apply network port forwarding rules
    #
    if True:    # NAT
        pass
    else:       # bridge
        vm_address = '192.168.0.46'
        ssh_port = '22'
        ssh_user = 'muppy'
        print "ssh command:"
        print "ssh -p %s %s@%s" % (ssh_port, ssh_user, vm_address )
        return execlp('ssh', 'ssh', "-p %s %s@%s" % (ssh_port, ssh_user, vm_address))


def main():
    usage = "Usage %prog [options]"

    parser = argparse.ArgumentParser(prog=__program__, version=__version__, description=__description__)
    subparsers = parser.add_subparsers(help='sub-command help', dest="subparser_name")
    parser.add_argument('-c', '--config', type=str, help="path to a muppy configuration file. Defaults to ~/.muppyrc", default="~/.muppy_rc")

    # base-vm subcommand
    parser_basevms = subparsers.add_parser('basevms', help='Manages base VMs.')

    # init sub-command
    parser_init = subparsers.add_parser('init', help='Initializes a VM from a base VM.')

    # up sub-command
    parser_up = subparsers.add_parser('up', help='Starts a VM.', )
    parser_up.add_argument('-n', '--name', type=str, dest='vm_name', help="Name of VM to launch, required only if this is a muppy cluster")
    parser_up.add_argument('--gui', default=False, action='store_true', help="Launch with a GUI. Default is headless.")

    # ssh sub-command
    parser_ssh = subparsers.add_parser('ssh', help='Connect to the VM using SSH.')

    # down sub-command
    parser_down = subparsers.add_parser('down', help='Stops a VM.')

    # destroy sub-command
    parser_destroy = subparsers.add_parser('destroy', help='Destroys a VM.')

    args = parser.parse_args()

    # TODO: check that if we are there args.subparser_name is alwayd valid
    assert args.subparser_name

    getattr(sys.modules[__name__], args.subparser_name)(args)

    print "fini"


    # parser = OptionParser(usage, prog='mup.py', version=__version__, description=__description__)
    #
    # # call(['VBoxManage', 'import', box_file, '--vsys', '0', '--vmname', new_vm_name])
    # common = OptionGroup(parser, "init", "Initialize a new VM")
    # common.add_option('-b', '--box', dest='box_file',
    #                   default='localhost',
    #                   help='Indicate the name of the box to clone. (default: muppy-precise-64-fr)')
    # common.add_option('-n', '--vm-name', dest='new_vm_name',
    #                   default=8069,
    #                   help='Name of the new VM (default: box_file_{{mac address}})')
    # parser.add_option_group(common)
    #
    #
    #
    #
    # group = OptionGroup(parser, 'Multi company default',
    #                 "Application option")
    # group.add_option('-m', '--model', dest='model',
    #                 default='res.partner',
    #                 help='Enter the model name to check'),
    # #group.add_option('-c', '--company', dest='company',
    # #                default='',
    # #                help='Enter list of companies, seprate by a comma (,)')
    # group.add_option('-a', '--all', dest='all',
    #                 action='store_true',
    #                 default=False,
    #                 help='Extract field if value is False, or blank')
    # group.add_option('', '--header', dest='header',
    #                 action='store_true',
    #                 default=False,
    #                 help='Add XML and OpenObkect Header')
    # group.add_option('', '--indent', dest='indent',
    #                 action='store_true',
    #                 default=False,
    #                 help='Indent the XML output')
    # group.add_option('', '--with-inactive', dest='inactive',
    #                  action='store_true',
    #                  default=False,
    #                  help='Extract inactive records')
    # group.add_option('', '--id', dest='id', type=int,
    #                  default=False,
    #                  help='Indicate which ID you want to extract')
    # group.add_option('', '--ids', dest='ids', type=str,
    #                  default=False,
    #                  help='Indicate which IDs you want to extract   --ids=id1,id2,...,idn')
    # group.add_option('', '--domain', dest='domain', type=str,
    #                  default=False,
    #                  help='''Indicate which domain search the object   --domain="[('','','')]"''')
    # group.add_option('', '--follow-one2many', dest='one2many',
    #                  action='store_true',
    #                  default=False,
    #                  help='Follow the one2many child of this record')
    # parser.add_option_group(group)
    #
    # opts, args = parser.parse_args()

if __name__ == '__main__':
    main()

    #VBoxManage import ~/Documents/muppet-precise-64-fr.ova --vsys 0 --vmname toto@234
    #from subprocess import call
    #call(['VBoxManage', 'import', box_file, '--vsys', '0', '--vmname', new_vm_name])


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

# Récupérer l'ip 
# VBoxManage guestproperty get "muppet-precise-64-fr" "/VirtualBox/GuestInfo/Net/0/V4/IP"


# VBoxManage modifyvm "VM name" --natpf1 "guestssh,tcp,,2222,,22"
# With the above example, all TCP traffic arriving on port 2222 on any host interface will be forwarded to port 22 in the guest. The protocol name tcp is a mandatory attribute defining which protocol should be used for forwarding (udp could also be used). The name guestssh is purely descriptive and will be auto-generated if omitted. The number after --natpf denotes the network card, like in other parts of VBoxManage.

#To remove this forwarding rule again, use the following command:
#VBoxManage modifyvm "VM name" --natpf1 delete "guestssh"


