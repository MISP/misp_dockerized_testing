#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from subprocess import Popen
import shlex
from pathlib import Path
import time

nginx_root = Path('nginx-proxy')
cur_dir = os.getcwd()
os.chdir(nginx_root)
command = shlex.split('sudo docker-compose up -d')
p = Popen(command)
p.wait()
time.sleep(5)
command = shlex.split('sudo docker exec nginx-proxy /bin/cat /etc/nginx/conf.d/default.conf')
p = Popen(command)
p.wait()
os.chdir(cur_dir)
