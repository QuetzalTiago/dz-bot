chmod -R 777 /dz-bot/
aws ssm get-parameter --name "bot-config.json" --query "Parameter.Value" --output text > /dz-bot/config.json