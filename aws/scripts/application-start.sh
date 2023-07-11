source ~/.bashrc
sudo apt update -y
sudo apt install -y python3-pip ffmpeg
sudo pip3 install -r /dz-bot/requirements.txt
python3 /dz-bot/bot.py