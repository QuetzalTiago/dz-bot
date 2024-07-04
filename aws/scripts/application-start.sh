#!/bin/bash

python3 -m pip install -r /dz-bot/requirements.txt
cd /dz-bot/
python3 bot.py > output.txt 2> error.txt < /dev/null &
