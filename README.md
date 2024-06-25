# Discord Bot

This Discord bot is designed to provide both entertainment and utility functionalities to the users of a Discord server. The bot is designed in Python using the Discord.py library and is highly modular with a distinct set of services handling its diverse functionalities.

## Features:

### 1. **Music Commands:**

- **Play**: The bot can play songs in a voice channel. Trigger this functionality with either `play [song_name/link]` or `p [song_name/link]`.
- **Skip**: If you're not in the mood for the current song, simply skip it with `skip` or `s`.

- **Loop**: Want to keep listening to the same song? Use `loop` to loop the current song.

- **Stop**: If you want the bot to stop playing music and leave the channel, use `stop`.

- **Clear**: Clear the current queue with the `clear` command.

- **Queue**: Check the current songs in the queue with `queue` or `q`.

### 2. **Utility Commands:**

- **Purge**: Need to clean up the chat? Use the `purge` command to clean up the bot's messages and commands requested.

- **Restart**: You can restart the bot using the `restart` command.

- **Help**: If you need a list of all the available commands and their functionalities, just type `help`.

- **Btc**: Check the current Bitcoin price with `btc`.

- **Emoji**: Enhance your messages with the `emoji` command.

- **Chess**: Challenge your friends to a game of chess with the `chess` command.

## Setup:

1. To set up the bot, you need a `config.json` file with your Discord token in the following format:

```json
{
  "secrets": {
    "discordToken": "YOUR_DISCORD_TOKEN"
    ...
  }
}
```

2. Run the main bot script to initialize and bring the bot online.

## Diagram

![DZ-Bot Diagram](https://github.com/QuetzalTiago/dz-bot/blob/main/diagram.png)
