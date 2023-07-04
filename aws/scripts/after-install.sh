#!/bin/bash
for file in /dz-bot/bot/config/*.example.json; do mv -- "$file" "${file//.example/}"; done
aws ssm get-parameter --name "bot-config.json" --query "Parameter.Value" --output text > /dz-bot/bot/config.json