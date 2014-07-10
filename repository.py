# coding: utf-8
import os
from fabric import  colors

class Repository(object):
    def __init__(self, user, password, url, base_path):
        self.dvcs, self.clone_url, self.destination_directory, self.version, self.name, \
            self.owner, self.protocol = Repository.parse_appserver_url(url)
        self.url = url
        self.user = user
        self.password = password

        self.base_path = base_path

    @staticmethod
    def parse_appserver_url(url):
        """
        Accept a appserver_url of the form: {dvcs} {clone_url} [destination_directory] [version]
        :returns a list of 7 elements:
        [
            dvcs,
            clone_url,
            destination_directory,
            version,
            repository_name,
            owner_name,
            protocol
        ]
        """
        ret_list = [None] * 7  # Create a list of 7 None elements

        url_components = url.split(' ')
        ret_list[0:len(url_components)] = url_components  # Feed what we can

        if ret_list[0] not in ('git', 'hg'):
            print colors.red("Error: unsupported dvcs : %s. Must be 'hg' or 'git'." % ret_list[0])

        # we extrace repository name from url
        if ret_list[0] == 'git':
            if ret_list[1].startswith('git'):
                owner_name = ret_list[1].split(':')[1].split('/')[0]
                repository_name = ret_list[1].split(':')[1].split('/')[-1][:-4]
            else:
                # https
                owner_name = ret_list[1].split('/')[-2]
                repository_name = ret_list[1].split('/')[-1][:-4]
        else:
            # mercurial
            owner_name = ret_list[1].split('/')[-2]
            repository_name = ret_list[1].split('/')[-1]

        ret_list[4] = repository_name
        ret_list[5] = owner_name

        # protocol
        protocol_prefix = ret_list[1][:3]
        ret_list[6] = 'ssh' if protocol_prefix in ('git', 'ssh',) else 'https'

        # let destination_directory to repository_name if undefined
        ret_list[2] = ret_list[2] or ret_list[4]

        return ret_list

    @property
    def hostname(self):
        if self.clone_url.startswith('git'):
            return self.clone_url.split(':')[0].split('@')[1]
        elif self.clone_url.startswith('http'):
            subs = self.clone_url.split('//')[1].split('/')[0]
            if subs.find('@') > 0:
                return subs.split('@')[1]
            return subs
        elif self.clone_url.startswith('ssh'):
            return self.clone_url.split('//')[1].split('/')[0].split('@')[1]
        return ''

    @property
    def path(self):
        return os.path.join(self.base_path, self.destination_directory)

    def get_refspec_command_line(self):
        """Returns shell command to retrieve current active revision in repository"""
        if self.dvcs == 'git':
            return 'git rev-parse --verify HEAD'
        elif self.dvcs == 'hg':
            # mercurial
            return 'hg id -i'

    def get_show_current_rev_command_line(self):
        """Returns shell command to display info about current revision in repository"""
        if self.dvcs == 'git':
            return 'git show --format=medium -s HEAD'
        elif self.dvcs == 'hg':
            return 'hg sum'

    def get_fetch_command_line(self, source=''):
        """Returns a git fetch or hg pull command line"""
        if self.dvcs == 'git':
            return 'git fetch origin %s' % source
        elif self.dvcs == 'hg':  # mercurial
            return 'hg pull %s' % source

    def get_checkout_command_line(self, refspec):
        """Returns a git checkout or hg update command line"""
        if self.dvcs == 'git':
            return 'git checkout %s' % refspec
        elif self.dvcs == 'hg':  # mercurial
            return 'hg update %s' % refspec
