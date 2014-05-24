# coding: utf-8

from repository import Repository
from fabric import colors
import requests

class BitbucketRepository(Repository):

    def __init__(self, user, password, url, base_path):
        super(BitbucketRepository, self).__init__(user, password, url, base_path)

    def search_deployment_key(self, key_name=''):
        if not key_name:
            return []
        url = "https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (self.owner, self.name)
        response = requests.get(url, auth=(self.user, self.password))
        if response.status_code != requests.codes.ok:
            return []

        key_list = response.json()
        result = [key['pk'] for key in key_list if str(key['label']) == key_name]
        return result

    def post_deployment_key(self, key_name, key_string):
        """
        Upload a deployment key to repo
        :param key_name: Name of the key to upload (bitbucket's label).
        :type key_name: str
        :param key_string: SSH Key
        :type key_string: str
        :return: True or False
        :rtype: boolean
        """
        url = "https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/" % (self.owner, self.name,)
        auth = (self.user, self.password,)
        data = {
            'label': key_name,
            'key': key_string
        }
        res = requests.post(url, auth=auth, data=data)
        if res.status_code != requests.codes.ok:
            print red("Error: Unable to upload deployment key to bitbucket.")
            return False
        return True

    def delete_deployment_key(self, pk):
        """
        Delete deployment key
        :param pk: a bitbucket pk
        :type pk: str or int
        :return: True or False
        :rtype: boolean
        """
        url = "https://api.bitbucket.org/1.0/repositories/%s/%s/deploy-keys/%s" % (self.owner, self.name, pk)
        auth = (self.user, self.password,)
        response = requests.delete(url, auth=auth)
        if response.status_code != 204:  # Bitbucket : WTF 204 ?? !!!!
            return False
        return True

    def update_deployment_key(self, key_name, key_string):
        """
        Delete existing deployment keys named as key_name, then upload a new one
        :param key_name: Name of the key to update (bitbucket's label).
        :type key_name: str
        :param key_string: SSH Key
        :type key_string: str
        :return: True or False
        :rtype: boolean
        """
        # for update, we don't bother if key do not exists
        keys = self.search_deployment_key(key_name)
        for key in keys:
            self.delete_deployment_key(key)
        return self.post_deployment_key(key_name, key_string)

    @property
    def clone_command_line(self):
        if self.dvcs == 'hg':
            if self.version:
                return "hg clone -y -r %s %s %s" % (self.version, self.clone_url, self.destination_directory,)
            return "hg clone -y %s %s" % (self.clone_url, self.destination_directory,)

        # elif self.dvcs == 'git':
        return "git clone %s %s" % (self.clone_url, self.destination_directory,)

    @property
    def checkout_command_line(self):
        if not self.version:
            return ''
        if self.dvcs == 'hg':
            return "hg update %s" % (self.version,)
        # elif self.dvcs == 'git':
        return "git checkout %s" % (self.version,)

    @property
    def pull_command_line(self):
        if self.dvcs == 'hg':
            return "hg pull -u'"
        # elif self.dvcs == 'git':
        return "git pull origin master"

