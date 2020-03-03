#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
import shlex
import os
import git
from config import docker_setup

print("Docker requires sudo. unlock sudo in the teminal you are running that script or it's gonna fail: sudo -d / exit.")

# Update repositories
for root_dir in docker_setup:
    cur_dir = os.getcwd()
    os.chdir(root_dir)
    repo = git.Repo('.')
    repo.git.checkout('docker-compose.yml')
    repo.remote('origin').pull()
    os.chdir(cur_dir)


# Set different ports for each image
for root_dir, values in docker_setup.items():
    with (root_dir / 'docker-compose.yml').open() as f:
        docker_content = f.read()
    docker_content = docker_content.replace('80:80', values['http_port'])
    docker_content = docker_content.replace('443:443', values['https_port'])

    # Add refresh script
    if docker_content.find('misp-refresh') < 0:
        docker_content = docker_content.replace('volumes:', 'volumes:\n      - "../misp-refresh:/var/www/MISP/misp-refresh/"')

    # Add network configuration so all the containers are on the same
    if docker_content.find('networks') < 0:
        docker_content = docker_content.replace('#      - "NOREDIR=true" #Do not redirect port 80', '      - "NOREDIR=true" #Do not redirect port 80\n    networks:\n        - default\n        - misp-test-sync')
        docker_content += '\nnetworks:\n    misp-test-sync:\n        external:\n            name: custom_misp_test_sync\n'

    with (root_dir / 'docker-compose.yml').open('w') as f:
        f.write(docker_content)

for root_dir, values in docker_setup.items():
    cur_dir = os.getcwd()
    os.chdir(root_dir)
    # Build the dockers
    command = shlex.split('sudo docker-compose -f docker-compose.yml -f build-docker-compose.yml build')
    p = Popen(command)
    p.wait()
    # Create network
    command = shlex.split('sudo docker network create custom_misp_test_sync')
    p = Popen(command)
    p.wait()
    # Run the dockers
    command = shlex.split('sudo docker-compose up -d')
    p = Popen(command)
    p.wait()
    # Set baseurl
    command = shlex.split(f'sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake baseurl {values["baseurl"]}')
    p = Popen(command)
    p.wait()
    # Init admin user
    command = shlex.split('sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake userInit')
    p = Popen(command)
    p.wait()
    # Run DB updates
    command = shlex.split('sudo docker-compose exec --user www-data misp /bin/bash /var/www/MISP/app/Console/cake Admin runUpdates')
    p = Popen(command)
    p.wait()
    # Set the admin key
    command = shlex.split(f'sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake admin change_authkey admin@admin.test {values["admin_key"]}')
    p = Popen(command)
    p.wait()
    # Get IP on docker
    # # Get thing to inspect
    command = shlex.split('sudo docker-compose ps -q misp')
    p = Popen(command, stdout=PIPE)
    thing = p.communicate()[0].decode().strip()
    command = shlex.split('sudo docker inspect -f "{{.NetworkSettings.Networks.custom_misp_test_sync.IPAddress}}"')
    command.append(thing)
    p = Popen(command, stdout=PIPE)
    out = p.communicate()[0].decode().strip()
    with open('current_ip_docker', 'w') as f:
        f.write(out)
    os.chdir(cur_dir)
