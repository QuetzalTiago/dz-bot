pip3 install -r /dz-bot/requirements.txt
cd /dz-bot/
python3 bot.py > output.txt 2> error.txt < /dev/null &
