aws ssm get-parameter --name "bot-config.json" --query "Parameter.Value" --output text > /dz-bot/config.json
pip3 install -r /dz-bot/requirements.txt
python3 /dz-bot/bot.py