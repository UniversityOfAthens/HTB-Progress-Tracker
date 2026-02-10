# HTB Progress Tracker

A Discord bot that tracks your Hack The Box (HTB) progress throughout the week and provides weekly reports, leaderboards, and automated reset scheduling.

## Features

- **User Tracking**: Track HTB users by their User ID via DM
- **Weekly Goals**: Set targets for machines and challenges (default: 1 machine, 2 challenges)
- **Activity Monitoring**: Automatically detects user/root flags and challenge solves
- **Weekly Report**: Generates a summary every Saturday at 21:00 (Greek time)
- **Leaderboard**: Shows top 10 hackers ranked by total solves and streak
- **Personal Stats**: Users can check their own progress anytime
- **Streak Tracking**: Tracks consecutive weeks of meeting goals

## Commands

| Command | Description |
|---------|-------------|
| `!track` | Start tracking your HTB account via DM |
| `!untrack` | Stop tracking your HTB account |
| `!stats` | View your personal weekly progress |
| `!top` | View the weekly leaderboard |
| `!reset_week` | (Admin) Manually trigger weekly reset |

## Setup

### Option 1: Using Nix (Recommended)

If you have [Nix](https://nixos.org/) installed with [flakes](https://nixos.org/manual/nix/stable/command-ref/new-cli/nix3-flake.html) enabled:

```bash
nix develop
```

This will enter a shell with all dependencies installed automatically.

### Option 2: Manual Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/UniversityOfAthens/HTB-Progress-Tracker.git
   cd HTB-Progress-Tracker
   ```

2. **Install dependencies**
   ```bash
   pip install discord.py requests python-dotenv
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your credentials:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   HTB_API_TOKEN=your_htb_api_token
   CHANNEL_ID=your_discord_channel_id
   HTB_API_URL="https://labs.hackthebox.com"
   ```

4. **Run the bot**
   ```bash
   python3 bot.py
   ```

## Configuration

Edit the constants in `bot.py` to customize:
```python
GOAL_MACHINES = 1   # Weekly machine goal
GOAL_CHALLENGES = 2 # Weekly challenge goal
```

## Utilities

### Update Root Flags Manually

If you need to sync root flags without waiting for the weekly reset:

```bash
python3 utils/update_root_flags.py
```

## Project Structure

```
HTB-Progress-Tracker/
├── bot.py                     # Main Discord bot
├── utils/
│   └── update_root_flags.py   # Utility for manual root flag updates
├── htb_data.json              # Database file (auto-generated)
├── .env                       # Environment variables
├── .env.example               # Environment template
└── README.md                  # This file
```

## How It Works

1. Users run `!track` and provide their HTB User ID
2. The bot fetches their current activity to establish a baseline
3. Every 10 minutes, the bot checks for new activity (user flags, root flags, challenge solves)
4. When goals are met, the streak increases; otherwise, it resets
5. Every Saturday at 21:00 (Greek time), a weekly report is generated and sent to the configured channel
6. Users who missed their goals are publicly "shamed" with mentions

## Requirements

- Python 3.8+
- Discord.py
- requests
- python-dotenv

Or use [Nix](https://nixos.org/) with flakes for automatic dependency management:
```bash
nix develop
```

## License

MIT
