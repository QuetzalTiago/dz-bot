#!/bin/bash

python3.9 -m pip install -r /dz-bot/requirements.txt
cd /dz-bot/
python3.9 bot.py > output.txt 2> error.txt < /dev/null &
