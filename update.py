#!/usr/bin/env python

from os import path as opath, environ as env
from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from logging.handlers import RotatingFileHandler
from subprocess import run as srun

basicConfig(
    level=INFO,
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=50000000, backupCount=10),
        StreamHandler(),
    ],
)

UPSTREAM_REPO = env.get('UPSTREAM_REPO', "https://github.com/SilentDemonSD/Mkv-TBot")
UPSTREAM_BRANCH = env.get('UPSTREAM_BRANCH', "main")

if UPSTREAM_REPO is not None:
    if opath.exists('.git'):
        srun(["rm", "-rf", ".git"])
        
    update = srun([f"git init -q \
                     && git config --global user.email drxxstrange@gmail.com \
                     && git config --global user.name SilentDemonSD \
                     && git add . \
                     && git commit -sm update -q \
                     && git remote add origin {UPSTREAM_REPO} \
                     && git fetch origin -q \
                     && git reset --hard origin/{UPSTREAM_BRANCH} -q"], shell=True)

    if update.returncode == 0:
        log_info(f'Successfully updated with latest commit from {UPSTREAM_REPO}')
    else:
        log_error(f'Something went wrong while updating, check {UPSTREAM_REPO} if valid or not!')
