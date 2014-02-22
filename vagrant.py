from urlparse import urlparse
from fabric.api import *
from fabric.contrib.files import exists
from fabric.colors import *
import sys

from muppy_utils import *
"""
Setup a VM and package it as a box.
Starts from a fresh VM (with only ssh server installed)
This script don't bother to install Chef and Puppet requirements.
root_user and root_password come from the [env] section
"""

class _VagrantConfig:
    pass

def parse_config(config_parser):
    if config_parser.get('vagrant', 'install_vagrant') and eval(config_parser.get('vagrant', 'install_vagrant')):

      _VagrantConfig.user = config_parser.get('vagrant', 'user')
      _VagrantConfig.password = config_parser.get('vagrant', 'password')

#      _VagrantConfig.mysql_host = (config_parser.has_option('magento', 'mysql_host') \
#                                   and config_parser.get('magento', 'mysql_host')) \
#                                   or 'localhost'
#      if _MagentoConfig.api_key and not _MagentoConfig.enc_key:
#          print red("Error: missing enc_key.")
#          print red("Error: enc_key is required as you defined an api_key.")
#          sys.exit(1)

    return _VagrantConfig

def setup_vagrant_user():
    """Set up a virtualbox box for use with vagrant"""
    env.user = env.root_user
    env.password = env.root_password

    sudo("apt-get update --fix-missing")

    # Create vagrant user
    sudo("useradd -m -s /bin/bash %s" % (env.vagrant.user,))

    sudo('usermod -a -G sudo %s' % env.vagrant.user)

    user_set_password(env.vagrant.user, env.vagrant.password)

    sudo("sed -i -e '/Defaults\s\+env_reset/a Defaults\texempt_group=admin' /etc/sudoers")
    sudo("groupadd -r admin")
    sudo("usermod -a -G admin %s" % env.vagrant.user)
    sudo("sed -i -e 's/%admin ALL=(ALL) ALL/%admin ALL=(ALL) NOPASSWD:ALL/g' /etc/sudoers")

    # vagrant ssh key
    print blue("Installing Vagrant SSH public key"),
    ssh_path = "/home/%s/.ssh" % env.vagrant.user
    sudo("mkdir -p %s" % ssh_path)
    sudo("chown -R %s:%s %s" % (env.vagrant.user, env.vagrant.user, ssh_path))
    sudo("chmod 700 %s" % ssh_path)
    sudo("wget --no-check-certificate 'https://raw.github.com/mitchellh/vagrant/master/keys/vagrant.pub' -O %s/authorized_keys" % ssh_path)
    sudo("chown %s:%s %s/authorized_keys" % (env.vagrant.user, env.vagrant.user, ssh_path,))
    sudo("chmod 0600 %s/authorized_keys" % ssh_path)
    print green("ok")

def install_virtualbox_guest_additions(standalone=True):
    env.user = env.root_user
    env.password = env.root_password

    # Install VirtualBox Guest 
    sudo("apt-get -y install linux-headers-server build-essential dkms")
    print
    print blue("VirtualBox Guest Additions Installation")
    print
    print magenta("  First, check that VirtualBox Guest Additions ISO Image is connected to the VM.  But don't mount it !!!")
    print
    raw_input("  Press Enter to continue or CTRL-C to abandon.")
    sudo('mkdir -p /mnt/cdrom')
    sudo("mount /dev/cdrom /mnt/cdrom")
    sudo("sh /mnt/cdrom/VBoxLinuxAdditions.run", warn_only=True)
    sudo("umount /mnt/cdrom")
    
    # Seems we need this reboot cycle for Guest Tools Installation to be successfull
    reboot()
    sudo("/etc/init.d/vboxadd setup")
    reboot()

    # Keep dkms BUT Remove the linux headers to keep things pristine
    sudo("apt-get -y remove linux-headers-server build-essential")
    sudo("apt-get -y autoremove")
    sudo("apt-get -y clean")

    # record box buildtime
    sudo("date > /etc/vagrant_box_build_time")

    # Zero out the free space to save space in the final image
    sudo("dd if=/dev/zero of=/EMPTY bs=1M", warn_only=True)
    sudo("rm -f /EMPTY")
    sudo("poweroff")
    print
    print
    print green("Box is configured and ready to package.")
    print 
    if standalone:
        print magenta("Use:  fab command vagrant_package_box --base my-virtual-machine")
        print magenta("and you will get a package.box")
    return

@task
def build_base_box(vm_name=''):
    """:[[vm_name]] - Build a base box and package it if [[vm_name]] is supplied"""
    setup_vagrant_user()
    install_virtualbox_guest_additions(standalone=False)
    if vm_name:
        package_box(vm_name)

@task
def package_box(vm_name=''):
    """:vm_name - Package the VirtualBox designed by vm_name as vm_name.box"""
    if not vm_name:
        print "ERROR: Missing required VirtualBox VM name parameter"
        sys.exit(1)
    local("rm boxes/%s.box" % (vm_name,))
    local("vagrant package --base %s --output boxes/%s.box" % (vm_name, vm_name))
    print green("Box: \"./boxes/%s.box\" successfully generated." % vm_name)