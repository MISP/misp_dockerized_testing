#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

docker_setup = {
    Path('misp01'): {
        'admin_key': 'w2Ty14045vmKxV8It0t3HLmt1YxCTHQFchljzjVf',
        'http_port': '8081:80',
        'https_port': '4431:443',
        'baseurl': 'https://localhost:4431/',
        # For testing
        'orgname': 'First org',
        'email_site_admin': 'first@site-admin.local',
        'email_admin': 'first@org-admin.local',
        'email_user': 'first@user.local'
    },
    Path('misp02'): {
        'admin_key': '5L41TAgcHMalm98jfcU5mkVLvfuV8DFBGRAL3Fp1',
        'http_port': '8082:80',
        'https_port': '4432:443',
        'baseurl': 'https://localhost:4432/',
        # For testing
        'orgname': 'Second org',
        'email_site_admin': 'second@site-admin.local',
        'email_admin': 'second@org-admin.local',
        'email_user': 'second@user.local'
    },
    Path('misp03'): {
        'admin_key': 'SLjOOWN5rpujph7ZpevhAykKGyZyqann5vlrI1gD',
        'http_port': '8083:80',
        'https_port': '4433:443',
        'baseurl': 'https://localhost:4433/',
        # For testing
        'orgname': 'Third org',
        'email_site_admin': 'third@site-admin.local',
        'email_admin': 'third@org-admin.local',
        'email_user': 'third@user.local'
    }
}
