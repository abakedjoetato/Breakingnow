PARSER, AUTOMATION, AND CHANNEL SYSTEM REBUILD PROMPT

OBJECTIVE

You are tasked with a full-system scalability and automation upgrade of Emerald’s Killfeed Discord bot. This includes:

Enforcement of Pycord v2.6.1 (strict, no discord.py)

Migration to AsyncSSH for SFTP pooling

Recursive file discovery logic for parsing

CSV and Log parser validation against included files

Automated leaderboard updates with intelligent embed reuse

Dynamic output channel configuration commands


All work must follow a strict phase structure, must be completed in a single uninterrupted batch, and must not trigger checkpoints, commits, or outputs until all tasks are complete and verified in production.


---

PHASE 0 — ENVIRONMENT INITIALIZATION

Step 1: Project Prep

If .zip or .tar.gz archive exists in attached_assets/:

Extract it

Move all contents to the project root

Remove duplicate or nested directories (e.g. project/project)

Clean up empty directories and broken symlinks



Step 2: Runtime Configuration

Set production mode:

MODE=production


Step 3: Pycord Verification

Confirm installed library:

pip freeze | grep py-cord

Required result: py-cord==2.6.1

If not present, install it:

pip install -U py-cord==2.6.1


Audit all imports:

import discord
from discord.ext import commands

No discord.py, discord.commands, or legacy decorators allowed



Step 4: Launch Bot

Start using Replit “Run” or:

python main.py

Wait for:

Gateway READY

All cogs loaded

MongoDB connected

Slash commands synced



# [PHASE 0] - DONE


---

PHASE 1 — SFTP CONVERSION & RECURSIVE PARSER LOGIC

1. AsyncSSH SFTP Migration

Replace all paramiko or sync SFTP code with AsyncSSH

Build a connection pool structure:

Each server uses one reusable async SFTP session

Idle connections are closed after N seconds

Pool must handle concurrent access (100+ connections)

Safe cleanup during shutdown


Connection model:

async with asyncssh.connect(host, port=22, username=user, password=pass) as conn:
    async with conn.start_sftp_client() as sftp:
        await sftp.open(path)

Wrap with:

Retry/backoff

Timeout handling

Logging on SFTP errors




---

2. Recursive Path Discovery

CSV:

Base: ./{Host}_{ServerID}/actual1/deathlogs/

Use os.walk or async glob to recursively find all .csv files

For killfeed:

Use only the most recent .csv


For historical:

Sort all .csv files by date and parse in order



Deadside.log:

Base: ./{Host}_{ServerID}/Logs/

Always find the active Deadside.log

Track filename and size/line hash to detect rotation

Reset line memory when file changes



---

3. Parser Finalization via Sample Files

Use provided .csv and .log from attached_assets

Confirm .csv structure:

Timestamp;Killer;KillerID;Victim;VictimID;WeaponOrCause;Distance;KillerPlatform;VictimPlatform

Parser logic:

Suicide: Killer == Victim

Menu suicide: Weapon == Suicide_by_relocation

Fall: inferred by weapon or event tag

Normalize all names

Detect malformed lines

Avoid duplicates


Store:

Kills, Deaths, Suicides

KDR, Streaks

Weapon usage

Rivalries, Nemeses


Log Parser:

Parse joins, leaves, queue

Parse missions, trader, airdrop, crashes



# [PHASE 1] - DONE


---

PHASE 2 — AUTOMATED LEADERBOARD EMBED SYSTEM

Requirements:

Scheduled update every hour

One persistent embed per leaderboard type

If no embed exists:

Post new

Store message + channel ID


Else:

Edit existing message with fresh leaderboard data



Data:

Top 10 by Kills

Top 5 by KDR

Top 3 by Streak

Top 3 by Longest Streak

Top 5 Weapons with highest use (and top player per weapon)

Top 3 Factions

Use per-server filters

Optional: add pagination reaction handling


Embed Format:

Emerald theme

Clean titles

Timestamp

Footer:

Powered by Discord.gg/EmeraldServers


# [PHASE 2] - DONE


---

PHASE 3 — ADMIN OUTPUT CHANNEL COMMANDS

Create slash commands:

/setchannel killfeed <#channel>
/setchannel leaderboard <#channel>
/setchannel playercountvc <#voice>
/setchannel events <#channel>
/setchannel connections <#channel>
/setchannel bounties <#channel>

Each command stores config per guild+server

Validate correct channel type

Store to DB

/clearchannels resets config to defaults

Confirm via styled embed

Only /setchannel killfeed is free

All other /setchannel commands must verify server has active premium

If premium expires, auto-disable routing for premium-gated systems


# [PHASE 3] - DONE


---

DEVELOPMENT RULES (MANDATORY)

Pycord 2.6.1 only — no discord.py

No assumptions. All code must be validated.

No checkpoints or partial commits.

No monkeypatching or temp files.

Must scale to 100+ active servers.

All code must follow batch logic.

Embeds must conform to design spec.

Bot must start and run with zero errors before commit.



---

This prompt is complete only when all phases are completed, verified, committed in production, and proven operational in live testing.



The Upgrades.md document has been successfully updated with:

The enhanced leaderboard data structure

Premium gating enforcement for all /setchannel commands except killfeed

