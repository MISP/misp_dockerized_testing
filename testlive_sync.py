#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import unittest

import urllib3  # type: ignore
import logging

from pymisp import MISPEvent, MISPObject, MISPSharingGroup, Distribution

from .setup_sync import MISPInstances

logging.disable(logging.CRITICAL)
urllib3.disable_warnings()


class TestSync(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maxDiff = None
        cls.misp_instances = MISPInstances()

        ready = False
        while not ready:
            ready = True
            for i in cls.misp_instances.instances:
                settings = i.site_admin_connector.server_settings()
                if (not settings['workers']['default']['ok']
                        or not settings['workers']['prio']['ok']):
                    print(f'Not ready: {i}')
                    ready = False
            time.sleep(1)

    # @classmethod
    # def tearDownClass(cls):
    #   for i in cls.instances:
    #        i.cleanup()

    def test_simple_sync(self):
        '''Test simple event, push to one server'''
        event = MISPEvent()
        event.info = 'Event created on first instance - test_simple_sync'
        event.distribution = Distribution.all_communities
        event.add_attribute('ip-src', '1.1.1.1')
        try:
            source = self.misp_instances.instances[0]
            dest = self.misp_instances.instances[1]
            event = source.org_admin_connector.add_event(event)
            source.org_admin_connector.publish(event)
            source.site_admin_connector.server_push(source.synchronisations[dest.name], event)
            time.sleep(10)
            dest_event = dest.org_admin_connector.get_event(event.uuid)
            self.assertEqual(event.attributes[0].value, dest_event.attributes[0].value)

        finally:
            source.org_admin_connector.delete_event(event)
            dest.site_admin_connector.delete_event(dest_event)

    def test_sync_community(self):
        '''Simple event, this community only, pull from member of the community'''
        event = MISPEvent()
        event.info = 'Event created on first instance - test_sync_community'
        event.distribution = Distribution.this_community_only
        event.add_attribute('ip-src', '1.1.1.1')
        try:
            source = self.misp_instances.instances[0]
            dest = self.misp_instances.instances[1]
            event = source.org_admin_connector.add_event(event)
            source.org_admin_connector.publish(event)
            dest.site_admin_connector.server_pull(dest.synchronisations[source.name])
            time.sleep(10)
            dest_event = dest.org_admin_connector.get_event(event)
            self.assertEqual(dest_event.distribution, 0)
        finally:
            source.org_admin_connector.delete_event(event)
            dest.site_admin_connector.delete_event(dest_event)

    def test_sync_all_communities(self):
        '''Simple event, all communities, enable automatic push on two sub-instances'''
        event = MISPEvent()
        event.info = 'Event created on first instance - test_sync_all_communities'
        event.distribution = Distribution.all_communities
        event.add_attribute('ip-src', '1.1.1.1')
        try:
            source = self.misp_instances.instances[0]
            middle = self.misp_instances.instances[1]
            last = self.misp_instances.instances[2]
            server = source.site_admin_connector.update_server({'push': True}, source.synchronisations[middle.name].id)
            self.assertTrue(server.push)

            middle.site_admin_connector.update_server({'push': True}, middle.synchronisations[last.name].id)  # Enable automatic push to 3rd instance
            event = source.user_connector.add_event(event)
            source.org_admin_connector.publish(event)
            source.site_admin_connector.server_push(source.synchronisations[middle.name])
            time.sleep(30)
            middle_event = middle.user_connector.get_event(event.uuid)
            self.assertEqual(event.attributes[0].value, middle_event.attributes[0].value)
            last_event = last.user_connector.get_event(event.uuid)
            self.assertEqual(event.attributes[0].value, last_event.attributes[0].value)
        finally:
            source.org_admin_connector.delete_event(event)
            middle.site_admin_connector.delete_event(middle_event)
            last.site_admin_connector.delete_event(last_event)
            source.site_admin_connector.update_server({'push': False}, source.synchronisations[middle.name].id)
            middle.site_admin_connector.update_server({'push': False}, middle.synchronisations[last.name].id)

    def create_complex_event(self):
        event = MISPEvent()
        event.info = 'Complex Event'
        event.distribution = Distribution.all_communities
        event.add_tag('tlp:white')

        event.add_attribute('ip-src', '8.8.8.8')
        event.add_attribute('ip-dst', '8.8.8.9')
        event.add_attribute('domain', 'google.com')
        event.add_attribute('md5', '3c656da41f4645f77e3ec3281b63dd43')

        event.attributes[0].distribution = Distribution.your_organisation_only
        event.attributes[1].distribution = Distribution.this_community_only
        event.attributes[2].distribution = Distribution.connected_communities

        event.attributes[0].add_tag('tlp:red')
        event.attributes[1].add_tag('tlp:amber')
        event.attributes[2].add_tag('tlp:green')

        obj = MISPObject('file')

        obj.distribution = Distribution.connected_communities
        obj.add_attribute('filename', 'testfile')
        obj.add_attribute('md5', '3c656da41f4645f77e3ec3281b63dd44')
        obj.attributes[0].distribution = Distribution.your_organisation_only

        event.add_object(obj)

        return event

    def test_complex_event_push_pull(self):
        '''Test automatic push'''
        event = self.create_complex_event()
        try:
            source = self.misp_instances.instances[0]
            middle = self.misp_instances.instances[1]
            last = self.misp_instances.instances[2]
            source.site_admin_connector.update_server({'push': True}, source.synchronisations[middle.name].id)
            middle.site_admin_connector.update_server({'push': True}, middle.synchronisations[last.name].id)  # Enable automatic push to 3rd instance

            event = source.org_admin_connector.add_event(event)
            source.org_admin_connector.publish(event)
            time.sleep(15)
            event_middle = middle.user_connector.get_event(event.uuid)
            event_last = last.user_connector.get_event(event.uuid)
            self.assertEqual(len(event_middle.attributes), 2)  # attribute 3 and 4
            self.assertEqual(len(event_middle.objects[0].attributes), 1)  # attribute 2
            self.assertEqual(len(event_last.attributes), 1)  # attribute 4
            self.assertFalse(event_last.objects)
            # Test if event is properly sanitized
            event_middle_as_site_admin = middle.site_admin_connector.get_event(event.uuid)
            self.assertEqual(len(event_middle_as_site_admin.attributes), 2)  # attribute 3 and 4
            self.assertEqual(len(event_middle_as_site_admin.objects[0].attributes), 1)  # attribute 2
            # FIXME https://github.com/MISP/MISP/issues/4975
            # Force pull from the last one
            # last.site_admin_connector.server_pull(last.sync_servers[0])
            # time.sleep(6)
            # event_last = last.user_connector.get_event(event.uuid)
            # self.assertEqual(len(event_last.objects[0].attributes), 1)  # attribute 2
            # self.assertEqual(len(event_last.attributes), 2)  # attribute 3 and 4
            # Force pull from the middle one
            # middle.site_admin_connector.server_pull(last.sync_servers[0])
            # time.sleep(6)
            # event_middle = middle.user_connector.get_event(event.uuid)
            # self.assertEqual(len(event_middle.attributes), 3)  # attribute 2, 3 and 4
            # Force pull from the last one
            # last.site_admin_connector.server_pull(last.sync_servers[0])
            # time.sleep(6)
            # event_last = last.user_connector.get_event(event.uuid)
            # self.assertEqual(len(event_last.attributes), 2)  # attribute 3 and 4
        finally:
            source.org_admin_connector.delete_event(event)
            middle.site_admin_connector.delete_event(event_middle)
            last.site_admin_connector.delete_event(event_last)
            source.site_admin_connector.update_server({'push': False}, source.synchronisations[middle.name].id)
            middle.site_admin_connector.update_server({'push': False}, middle.synchronisations[last.name].id)

    def test_complex_event_pull(self):
        '''Test pull'''
        event = self.create_complex_event()
        try:
            source = self.misp_instances.instances[0]
            middle = self.misp_instances.instances[1]
            last = self.misp_instances.instances[2]

            event = source.org_admin_connector.add_event(event)
            source.org_admin_connector.publish(event)
            middle.site_admin_connector.server_pull(middle.synchronisations[source.name])
            time.sleep(15)
            last.site_admin_connector.server_pull(last.synchronisations[middle.name])
            time.sleep(15)
            event_middle = middle.user_connector.get_event(event.uuid)
            event_last = last.user_connector.get_event(event.uuid)
            self.assertEqual(len(event_middle.attributes), 3)  # attribute 2, 3 and 4
            self.assertEqual(len(event_middle.objects[0].attributes), 1)  # attribute 2
            self.assertEqual(len(event_last.attributes), 2)  # attribute 3, 4
            self.assertEqual(len(event_last.objects[0].attributes), 1)
            # Test if event is properly sanitized
            event_middle_as_site_admin = middle.site_admin_connector.get_event(event.uuid)
            self.assertEqual(len(event_middle_as_site_admin.attributes), 3)  # attribute 2, 3 and 4
            self.assertEqual(len(event_middle_as_site_admin.objects[0].attributes), 1)  # attribute 2
        finally:
            source.org_admin_connector.delete_event(event)
            middle.site_admin_connector.delete_event(event_middle)
            last.site_admin_connector.delete_event(event_last)

    def test_sharing_group(self):
        '''Test Sharing Group'''
        event = self.create_complex_event()
        try:
            source = self.misp_instances.instances[0]
            middle = self.misp_instances.instances[1]
            last = self.misp_instances.instances[2]
            source.site_admin_connector.update_server({'push': True}, source.synchronisations[middle.name].id)
            middle.site_admin_connector.update_server({'push': True}, middle.synchronisations[last.name].id)  # Enable automatic push to 3rd instance

            sg = MISPSharingGroup()
            sg.name = 'Testcases SG'
            sg.releasability = 'Testing'
            sharing_group = source.site_admin_connector.add_sharing_group(sg)
            source.site_admin_connector.add_org_to_sharing_group(sharing_group, middle.host_org.uuid)
            source.site_admin_connector.add_server_to_sharing_group(sharing_group, 0)  # Add local server
            # NOTE: the data on that sharing group *won't be synced anywhere*

            a = event.add_attribute('text', 'SG only attr')
            a.distribution = Distribution.sharing_group
            a.sharing_group_id = sharing_group.id

            event = source.org_admin_connector.add_event(event)
            source.org_admin_connector.publish(event)
            time.sleep(60)

            event_middle = middle.user_connector.get_event(event)
            self.assertTrue(isinstance(event_middle, MISPEvent), event_middle)
            self.assertEqual(len(event_middle.attributes), 2, event_middle)
            self.assertEqual(len(event_middle.objects), 1, event_middle)
            self.assertEqual(len(event_middle.objects[0].attributes), 1, event_middle)

            event_last = last.user_connector.get_event(event)
            self.assertTrue(isinstance(event_last, MISPEvent), event_last)
            self.assertEqual(len(event_last.attributes), 1)
            # Test if event is properly sanitized
            event_middle_as_site_admin = middle.site_admin_connector.get_event(event.uuid)
            self.assertEqual(len(event_middle_as_site_admin.attributes), 2)
            event_last_as_site_admin = last.site_admin_connector.get_event(event.uuid)
            self.assertEqual(len(event_last_as_site_admin.attributes), 1)
            # Get sharing group from middle instance
            sgs = middle.site_admin_connector.sharing_groups()
            self.assertEqual(len(sgs), 0)

            # TODO: Update sharing group so the attribute is pushed
            # self.assertEqual(sgs[0].name, 'Testcases SG')
            # middle.site_admin_connector.delete_sharing_group(sgs[0])
        finally:
            source.org_admin_connector.delete_event(event)
            middle.site_admin_connector.delete_event(event)
            last.site_admin_connector.delete_event(event)
            source.site_admin_connector.delete_sharing_group(sharing_group.id)
            middle.site_admin_connector.delete_sharing_group(sharing_group.id)
            source.site_admin_connector.update_server({'push': False}, source.synchronisations[middle.name].id)
            middle.site_admin_connector.update_server({'push': False}, middle.synchronisations[last.name].id)
