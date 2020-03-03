#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from config import docker_setup
from subprocess import Popen
import shlex

print("Docker requires sudo. unlock sudo in the teminal you are running that script or it's gonna fail: sudo -d / exit.")

for root_dir in docker_setup:
    cur_dir = os.getcwd()
    os.chdir(root_dir)
    command = shlex.split('sudo docker-compose stop')
    p = Popen(command)
    p.wait()
    os.chdir(cur_dir)
