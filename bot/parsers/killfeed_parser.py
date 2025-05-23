"""
Emerald's Killfeed - Killfeed Parser (PHASE 2)
Parses CSV files for kill events and generates embeds
"""

import asyncio
import csv
import logging
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

import aiofiles
import asyncssh
import os
import glob
from discord.ext import commands

logger = logging.getLogger(__name__)

class KillfeedParser:
    """
    KILLFEED PARSER (FREE)
    - Runs every 300 seconds
    - SFTP path: ./{host}_{serverID}/actual1/deathlogs/*/*.csv
    - Loads most recent file only
    - Tracks and skips previously parsed lines
    - Suicides normalized (killer == victim, Suicide_by_relocation → Menu Suicide)
    - Emits killfeed embeds with distance, weapon, styled headers
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.parsed_lines: Dict[str, Set[str]] = {}  # Track parsed lines per server
        self.last_file_position: Dict[str, int] = {}  # Track file position per server
        self.sftp_pool: Dict[str, asyncssh.SSHClientConnection] = {}  # SFTP connection pool
        self.pool_cleanup_timeout = 300  # 5 minutes idle timeout
        
    async def parse_csv_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single CSV line into kill event data"""
        try:
            # Expected CSV format: Timestamp;Killer;KillerID;Victim;VictimID;WeaponOrCause;Distance;KillerPlatform;VictimPlatform
            parts = line.strip().split(';')
            if len(parts) < 9:
                return None
                
            timestamp_str, killer, killer_id, victim, victim_id, weapon, distance, killer_platform, victim_platform = parts[:9]
            
            # Parse timestamp - format: 2025.04.30-00.16.49
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y.%m.%d-%H.%M.%S')
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            except ValueError:
                # Fallback format
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if not timestamp.tzinfo:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            # Normalize suicide events
            is_suicide = killer == victim or weapon.lower() == 'suicide_by_relocation'
            if is_suicide:
                if weapon.lower() == 'suicide_by_relocation':
                    weapon = 'Menu Suicide'
                elif weapon.lower() == 'falling':
                    weapon = 'Falling'
                    is_suicide = True  # Falling is treated as suicide
                else:
                    weapon = 'Suicide'
            
            # Parse distance
            try:
                distance_float = float(distance) if distance and distance != 'N/A' else 0.0
            except ValueError:
                distance_float = 0.0
            
            return {
                'timestamp': timestamp,
                'killer': killer,
                'killer_id': killer_id,
                'victim': victim,
                'victim_id': victim_id,
                'weapon': weapon,
                'distance': distance_float,
                'killer_platform': killer_platform,
                'victim_platform': victim_platform,
                'is_suicide': is_suicide,
                'raw_line': line.strip()
            }
            
        except Exception as e:
            logger.error(f"Failed to parse CSV line '{line}': {e}")
            return None
    
    async def get_sftp_connection(self, server_config: Dict[str, Any]) -> Optional[asyncssh.SSHClientConnection]:
        """Get or create SFTP connection with pooling"""
        try:
            sftp_host = server_config.get('sftp_host')
            sftp_port = server_config.get('sftp_port', 22)
            sftp_username = server_config.get('sftp_username')
            sftp_password = server_config.get('sftp_password')
            
            if not all([sftp_host, sftp_username, sftp_password]):
                logger.warning(f"SFTP credentials not configured for server {server_config.get('server_id', 'unknown')}")
                return None
            
            pool_key = f"{sftp_host}:{sftp_port}:{sftp_username}"
            
            # Check if connection exists and is still valid
            if pool_key in self.sftp_pool:
                conn = self.sftp_pool[pool_key]
                if not conn.is_client() or conn._transport.is_closing():
                    del self.sftp_pool[pool_key]
                else:
                    return conn
            
            # Create new connection with retry/backoff
            for attempt in range(3):
                try:
                    conn = await asyncio.wait_for(
                        asyncssh.connect(
                            sftp_host,
                            port=sftp_port,
                            username=sftp_username,
                            password=sftp_password,
                            known_hosts=None
                        ),
                        timeout=30
                    )
                    self.sftp_pool[pool_key] = conn
                    logger.info(f"Created SFTP connection to {sftp_host}")
                    return conn
                    
                except (asyncio.TimeoutError, asyncssh.Error) as e:
                    logger.warning(f"SFTP connection attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
            return None
            
        except Exception as e:
            logger.error(f"Failed to get SFTP connection: {e}")
            return None

    async def get_sftp_csv_files(self, server_config: Dict[str, Any]) -> List[str]:
        """Get CSV files from SFTP server using AsyncSSH with connection pooling"""
        try:
            conn = await self.get_sftp_connection(server_config)
            if not conn:
                return []
            
            server_id = server_config.get('server_id', 'unknown')
            sftp_host = server_config.get('sftp_host')
            remote_path = f"./{sftp_host}_{server_id}/actual1/deathlogs/"
            
            async with conn.start_sftp_client() as sftp:
                # Recursive file discovery using os.walk equivalent
                csv_files = []
                
                async def scan_directory(path):
                    try:
                        async for entry in sftp.scandir(path):
                            if entry.attrs.type == asyncssh.FILETYPE_DIRECTORY:
                                await scan_directory(f"{path}/{entry.filename}")
                            elif entry.filename.endswith('.csv'):
                                csv_files.append((f"{path}/{entry.filename}", entry.attrs.mtime))
                    except FileNotFoundError:
                        logger.warning(f"Directory not found: {path}")
                    except Exception as e:
                        logger.warning(f"Error scanning {path}: {e}")
                
                await scan_directory(remote_path)
                
                if not csv_files:
                    return []
                
                # Sort by modification time, get most recent
                csv_files.sort(key=lambda x: x[1], reverse=True)
                most_recent_file = csv_files[0][0]
                
                # Read file content
                try:
                    async with sftp.open(most_recent_file, 'r') as f:
                        file_content = await f.read()
                        return [line.strip() for line in file_content.splitlines() if line.strip()]
                except Exception as e:
                    logger.error(f"Failed to read CSV file {most_recent_file}: {e}")
                    return []
            
        except Exception as e:
            logger.error(f"Failed to fetch SFTP CSV files: {e}")
            return []
    
    async def get_dev_csv_files(self) -> List[str]:
        """Get CSV files from attached_assets and dev_data directories for testing"""
        try:
            # Check attached_assets first
            attached_csv = Path('./attached_assets/2025.04.30-00.00.00.csv')
            if attached_csv.exists():
                async with aiofiles.open(attached_csv, 'r') as f:
                    content = await f.read()
                    return [line.strip() for line in content.splitlines() if line.strip()]
            
            # Fallback to dev_data
            csv_path = Path('./dev_data/csv')
            if csv_path.exists():
                csv_files = list(csv_path.glob('*.csv'))
                if csv_files:
                    most_recent = max(csv_files, key=lambda f: f.stat().st_mtime)
                    async with aiofiles.open(most_recent, 'r') as f:
                        content = await f.read()
                        return [line.strip() for line in content.splitlines() if line.strip()]
            
            logger.warning("No CSV files found in attached_assets or dev_data/csv/")
            return []
                
        except Exception as e:
            logger.error(f"Failed to read dev CSV files: {e}")
            return []
    
    async def process_kill_event(self, guild_id: int, server_id: str, kill_data: Dict[str, Any]):
        """Process a kill event and update database"""
        try:
            # Add kill event to database
            await self.bot.db_manager.add_kill_event(guild_id, server_id, kill_data)
            
            if kill_data['is_suicide']:
                # Handle suicide - only increment suicide count
                await self.bot.db_manager.update_pvp_stats(
                    guild_id, server_id, kill_data['victim'],
                    {"$inc": {"suicides": 1}}
                )
            else:
                # Handle actual PvP kill - separate killer and victim stats
                # Update killer stats (increment kills)
                await self.bot.db_manager.update_pvp_stats(
                    guild_id, server_id, kill_data['killer'], 
                    {"$inc": {"kills": 1}}
                )
                
                # Update victim stats (increment deaths)
                await self.bot.db_manager.update_pvp_stats(
                    guild_id, server_id, kill_data['victim'],
                    {"$inc": {"deaths": 1}}
                )
            
            # Send killfeed embed
            await self.send_killfeed_embed(guild_id, kill_data)
            
        except Exception as e:
            logger.error(f"Failed to process kill event: {e}")
    
    async def send_killfeed_embed(self, guild_id: int, kill_data: Dict[str, Any]):
        """Send killfeed embed to designated channel"""
        try:
            import discord
            
            # Get guild configuration
            guild_config = await self.bot.db_manager.get_guild(guild_id)
            if not guild_config:
                return
            
            killfeed_channel_id = guild_config.get('channels', {}).get('killfeed')
            if not killfeed_channel_id:
                return
            
            channel = self.bot.get_channel(killfeed_channel_id)
            if not channel:
                return
            
            # Create styled embed based on death type
            weapon = kill_data['weapon'].lower()
            
            if kill_data['is_suicide']:
                # Check if it's a falling death
                if 'falling' in weapon or 'fall' in weapon:
                    title = "🪂 Falling Death"
                    description = f"**{kill_data['victim']}** fell to their death"
                    color = 0xFFA500  # Orange
                else:
                    title = "☠️ Player Reset"
                    description = f"**{kill_data['victim']}** reset their character"
                    color = 0x808080  # Gray
            else:
                title = "⚔️ Kill"
                description = f"**{kill_data['killer']}** eliminated **{kill_data['victim']}**"
                color = 0xFF4500  # Orange red
            
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=kill_data['timestamp']
            )
            
            # Add weapon and distance
            embed.add_field(
                name="🔫 Weapon", 
                value=kill_data['weapon'], 
                inline=True
            )
            
            if kill_data['distance'] > 0:
                embed.add_field(
                    name="📏 Distance", 
                    value=f"{kill_data['distance']:.1f}m", 
                    inline=True
                )
            
            # Add thumbnail from assets
            thumbnail_path = Path('./assets/Killfeed.png')
            if thumbnail_path.exists():
                # For production, you'd upload to a CDN. For now, use a placeholder
                embed.set_thumbnail(url="attachment://Killfeed.png")
            
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to send killfeed embed: {e}")
    
    async def parse_server_killfeed(self, guild_id: int, server_config: Dict[str, Any]):
        """Parse killfeed for a single server"""
        try:
            server_id = server_config.get('server_id', 'unknown')
            logger.info(f"Parsing killfeed for server {server_id} in guild {guild_id}")
            
            # Get CSV lines
            if self.bot.dev_mode:
                lines = await self.get_dev_csv_files()
            else:
                lines = await self.get_sftp_csv_files(server_config)
            
            if not lines:
                logger.warning(f"No CSV data found for server {server_id}")
                return
            
            # Track processed lines for this server
            server_key = f"{guild_id}_{server_id}"
            if server_key not in self.parsed_lines:
                self.parsed_lines[server_key] = set()
            
            new_events = 0
            
            for line in lines:
                if not line.strip() or line in self.parsed_lines[server_key]:
                    continue
                
                kill_data = await self.parse_csv_line(line)
                if kill_data:
                    await self.process_kill_event(guild_id, server_id, kill_data)
                    self.parsed_lines[server_key].add(line)
                    new_events += 1
            
            logger.info(f"Processed {new_events} new kill events for server {server_id}")
            
        except Exception as e:
            logger.error(f"Failed to parse killfeed for server {server_config}: {e}")
    
    async def run_killfeed_parser(self):
        """Run killfeed parser for all configured servers"""
        try:
            logger.info("Running killfeed parser...")
            
            # Get all guilds with configured servers
            guilds_cursor = self.bot.db_manager.guilds.find({})
            
            async for guild_doc in guilds_cursor:
                guild_id = guild_doc['guild_id']
                servers = guild_doc.get('servers', [])
                
                for server_config in servers:
                    await self.parse_server_killfeed(guild_id, server_config)
            
            logger.info("Killfeed parser completed")
            
        except Exception as e:
            logger.error(f"Failed to run killfeed parser: {e}")
    
    def schedule_killfeed_parser(self):
        """Schedule killfeed parser to run every 300 seconds"""
        try:
            self.bot.scheduler.add_job(
                self.run_killfeed_parser,
                'interval',
                seconds=300,  # 5 minutes
                id='killfeed_parser',
                replace_existing=True
            )
            logger.info("Killfeed parser scheduled (every 300 seconds)")
            
        except Exception as e:
            logger.error(f"Failed to schedule killfeed parser: {e}")
    
    async def cleanup_sftp_connections(self):
        """Clean up idle SFTP connections"""
        try:
            for pool_key, conn in list(self.sftp_pool.items()):
                if conn._transport.is_closing() or not conn.is_client():
                    del self.sftp_pool[pool_key]
                    logger.info(f"Cleaned up stale SFTP connection: {pool_key}")
        except Exception as e:
            logger.error(f"Failed to cleanup SFTP connections: {e}")