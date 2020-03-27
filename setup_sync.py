#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from pymisp import PyMISP, MISPOrganisation, MISPUser, MISPSharingGroup, MISPTag, MISPServer
import random
import string
import csv

from typing import List

from .generic_config import central_node_name, prefix_client_node, secure_connection


class MISPInstance():

    def __init__(self, misp_instance_dir: Path, secure_connection: bool):
        with (misp_instance_dir / 'config.json').open() as f:
            self.instance_config = json.load(f)

        print('Initialize', self.instance_config['admin_orgname'])
        self.secure_connection = secure_connection

        self.synchronisations = {}
        self.name = self.instance_config['admin_orgname']

        # NOTE: never use that user again after initial config.
        initial_user_connector = PyMISP(self.instance_config['baseurl'], self.instance_config['admin_key'], ssl=self.secure_connection, debug=False)
        # Set the default role (id 3 is normal user)
        initial_user_connector.set_default_role(3)
        initial_user_connector.toggle_global_pythonify()

        self.baseurl = self.instance_config['baseurl']
        self.external_baseurl = self.instance_config['external_baseurl']

        # Create organisation
        organisation = MISPOrganisation()
        organisation.name = self.instance_config['admin_orgname']
        self.host_org = initial_user_connector.add_organisation(organisation)
        if not isinstance(self.host_org, MISPOrganisation):
            # The organisation is probably already there
            organisations = initial_user_connector.organisations()
            for organisation in organisations:
                if organisation.name == self.instance_config['admin_orgname']:
                    self.host_org = organisation
                    break
            else:
                raise Exception('Unable to find admin organisation')

        # Create Site admin in new org
        user = MISPUser()
        user.email = self.instance_config['email_site_admin']
        user.org_id = self.host_org.id
        user.role_id = 1  # Site admin
        self.host_site_admin = initial_user_connector.add_user(user)
        if not isinstance(self.host_site_admin, MISPUser):
            users = initial_user_connector.users()
            for user in users:
                if user.email == self.instance_config['email_site_admin']:
                    self.host_site_admin = user
                    break
            else:
                raise Exception('Unable to find admin user')

        self.site_admin_connector = PyMISP(self.baseurl, self.host_site_admin.authkey, ssl=self.secure_connection, debug=False)
        self.site_admin_connector.toggle_global_pythonify()

        # Setup external_baseurl
        self.site_admin_connector.set_server_setting('MISP.external_baseurl', self.external_baseurl, force=True)
        # Setup baseurl
        self.site_admin_connector.set_server_setting('MISP.baseurl', self.baseurl, force=True)
        # Setup host org
        self.site_admin_connector.set_server_setting('MISP.host_org_id', self.host_org.id)

        # create other useful users
        self.orgadmin = self.create_user(self.instance_config['email_orgadmin'], 2)
        self.user = self.create_user(self.instance_config['email_user'], 3)
        # And connectors
        self.org_admin_connector = PyMISP(self.baseurl, self.orgadmin.authkey, ssl=self.secure_connection, debug=False)
        self.org_admin_connector.toggle_global_pythonify()
        self.user_connector = PyMISP(self.baseurl, self.user.authkey, ssl=self.secure_connection, debug=False)
        self.user_connector.toggle_global_pythonify()

    def __repr__(self):
        return f'<{self.__class__.__name__}(external={self.baseurl})>'

    def create_user(self, email, role_id):
        user = MISPUser()
        user.email = email
        user.org_id = self.host_org.id
        user.role_id = role_id
        new_user = self.site_admin_connector.add_user(user)
        if not isinstance(new_user, MISPUser):
            users = self.site_admin_connector.users()
            for user in users:
                if user.email == email:
                    new_user = user
                    break
            else:
                raise Exception('Unable to find admin user')
        return new_user

    def create_sync_user(self, organisation: MISPOrganisation) -> MISPServer:
        sync_org = self.site_admin_connector.add_organisation(organisation)
        if not isinstance(sync_org, MISPOrganisation):
            # The organisation is probably already there
            organisations = self.site_admin_connector.organisations(scope='all')
            for org in organisations:
                if org.name == organisation.name:
                    if not org.local:
                        org.local = True
                        org = self.site_admin_connector.update_organisation(org)
                    sync_org = org
                    break
            else:
                raise Exception('Unable to find sync organisation')

        short_org_name = sync_org.name.lower().replace(' ', '-')
        email = f"sync_user@{short_org_name}.local"
        user = MISPUser()
        user.email = email
        user.org_id = sync_org.id
        user.role_id = 5  # Sync user
        sync_user = self.site_admin_connector.add_user(user)
        if not isinstance(sync_user, MISPUser):
            users = self.site_admin_connector.users()
            for user in users:
                if user.email == email:
                    sync_user = user
                    break
            else:
                raise Exception('Unable to find sync user')

        sync_user_connector = PyMISP(self.site_admin_connector.root_url, sync_user.authkey, ssl=self.secure_connection, debug=False)
        return sync_user_connector.get_sync_config(pythonify=True)

    def configure_sync(self, server_sync_config: MISPServer):
        # Add sharing server
        for s in self.site_admin_connector.servers():
            if s.name == server_sync_config.name:
                server = s
                break
        else:
            server = self.site_admin_connector.import_server(server_sync_config)
        server.pull = True
        server.push = False
        server = self.site_admin_connector.update_server(server)
        r = self.site_admin_connector.test_server(server)
        if r['status'] != 1:
            raise Exception(f'Sync test failed: {r}')
        print(server)
        print(server.to_json(indent=2))
        # NOTE: this is dirty.
        self.synchronisations[server_sync_config.name.replace('Sync with ', '')] = server

    def add_tag_filter_sync(self, server_sync: MISPServer, name: str):
        # Add tag to limit push
        tag = MISPTag()
        tag.name = name
        tag.exportable = False
        tag.org_id = self.host_org.id
        tag = self.site_admin_connector.add_tag(tag)
        if not isinstance(tag, MISPTag):
            for t in self.site_admin_connector.tags():
                if t.name == name:
                    tag = t
                    break
            else:
                raise Exception('Unable to find tag')

        # Set limit on sync config
        filter_tag_push = {"tags": {'OR': [tag.id], 'NOT': []}, 'orgs': {'OR': [], 'NOT': []}}
        # filter_tag_pull = {"tags": {'OR': [], 'NOT': []}, 'orgs': {'OR': [], 'NOT': []}}
        server_sync.push_rules = json.dumps(filter_tag_push)
        # server.pull_rules = json.dumps(filter_tag_pull)
        server_sync = self.site_admin_connector.update_server(server_sync)

    def add_sharing_group(self, name: str, releasibility: str='Whatever it is a test',
                          servers: List[MISPServer]=[], organisations: List[MISPOrganisation]=[]):

        # Add sharing group
        for sg in self.site_admin_connector.sharing_groups():
            if sg.name == name:
                self.sharing_group = sg
                break
        else:
            sharing_group = MISPSharingGroup()
            sharing_group.name = name
            sharing_group.releasability = releasibility
            self.sharing_group = self.site_admin_connector.add_sharing_group(sharing_group)
            for server in servers:
                self.site_admin_connector.add_server_to_sharing_group(self.sharing_group, server)
            for organisation in organisations:
                self.site_admin_connector.add_org_to_sharing_group(self.sharing_group, organisation)


class MISPInstances():

    central_node_name = central_node_name
    prefix_client_node = prefix_client_node
    secure_connection = secure_connection

    def __init__(self, root_misps: str='misps'):
        self.misp_instances_dir = Path(root_misps)

        self.central_node = MISPInstance(self.misp_instances_dir / self.central_node_name, self.secure_connection)

        self.instances = []

        # Initialize all instances to sync with central node
        for path in sorted(self.misp_instances_dir.glob(f'{self.prefix_client_node}*')):
            if path.name == self.central_node_name:
                continue
            instance = MISPInstance(path, self.secure_connection)
            sync_server_config = self.central_node.create_sync_user(instance.host_org)
            print(sync_server_config.to_json())
            sync_server_config.name = f'Sync with {sync_server_config.Organisation["name"]}'
            instance.configure_sync(sync_server_config)
            self.instances.append(instance)

        # Create sync links for the instances among themselves.
        for instance_dest in self.instances:
            for instance_source in self.instances:
                if instance_dest == instance_source:
                    continue
                sync_server_config = instance_dest.create_sync_user(instance_source.host_org)
                sync_server_config.name = f'Sync with {sync_server_config.Organisation["name"]}'
                instance_source.configure_sync(sync_server_config)

    def dump_all_auth(self):
        auth = []
        for instance in self.instances + [self.central_node]:
            for user in instance.site_admin_connector.users():
                if user.change_pw == '1':
                    # Only change the password if the user never logged in.
                    password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                    instance.site_admin_connector.change_user_password(password, user)
                else:
                    password = 'Already changed by the user'
                a = {'url': instance.baseurl, 'login': user.email, 'authkey': user.authkey,
                     'password': password}
                auth.append(a)

        with (self.misp_instances_dir / 'auth.json').open('w') as f:
            json.dump(auth, f, indent=2)

        with (self.misp_instances_dir / 'auth.csv').open('w') as csvfile:
            fieldnames = ['url', 'login', 'authkey', 'password']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for a in auth:
                writer.writerow(a)


if __name__ == '__main__':
    instances = MISPInstances()
    instances.dump_all_auth()
    with (instances.misp_instances_dir / 'auth.json').open() as f:
        print(f.read())
    with (instances.misp_instances_dir / 'auth.csv').open() as f:
        print(f.read())
