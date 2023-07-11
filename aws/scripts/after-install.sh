#!/bin/bash
aws ssm get-parameter --name "bot-config.json" --query "Parameter.Value" --output text > /dz-bot/config.json