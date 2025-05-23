"""
Emerald's Killfeed - Historical Parser (PHASE 2)
Handles full historical data parsing and refresh operations
"""

import asyncio
import logging
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import aiofiles
import discord
from discord.ext import commands

from .killfeed_parser import KillfeedParser

logger = logging.getLogger(__name__)

class HistoricalParser:
    """
    HISTORICAL PARSER (FREE)
    - Triggered manually via /server refresh <server_id>
    - Or automatically 30s after /server add
    - Clears PvP data from that server
    - Parses all .csv files in order
    - Updates a single progress embed every 30s in the invoking channel
    - Does not emit killfeed embeds
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.killfeed_parser = KillfeedParser(bot)
        self.active_refreshes: Dict[str, bool] = {}  # Track active refresh operations
        
    async def get_all_csv_files(self, server_config: Dict[str, Any]) -> List[str]:
        """Get all CSV files for historical parsing"""
        try:
            if self.bot.dev_mode:
                return await self.get_dev_csv_files()
            else:
                return await self.get_sftp_csv_files(server_config)
                
        except Exception as e:
            logger.error(f"Failed to get CSV files: {e}")
            return []
    
    async def get_dev_csv_files(self) -> List[str]:
        """Get all CSV files from dev_data directory"""
        try:
            csv_path = Path('./dev_data/csv')
            csv_files = list(csv_path.glob('*.csv'))
            
            if not csv_files:
                logger.warning("No CSV files found in dev_data/csv/")
                return []
            
            all_lines = []
            
            # Sort files by name (assuming chronological naming)
            csv_files.sort()
            
            for csv_file in csv_files:
                async with aiofiles.open(csv_file, 'r') as f:
                    content = await f.read()
                    all_lines.extend(content.splitlines())
            
            return all_lines
            
        except Exception as e:
            logger.error(f"Failed to read dev CSV files: {e}")
            return []
    
    async def get_sftp_csv_files(self, server_config: Dict[str, Any]) -> List[str]:
        """Get all CSV files from SFTP server for historical parsing"""
        try:
            import paramiko
            import os
            
            # SFTP configuration
            sftp_host = os.getenv('SFTP_HOST', server_config.get('sftp_host'))
            sftp_port = int(os.getenv('SFTP_PORT', server_config.get('sftp_port', 22)))
            sftp_username = os.getenv('SFTP_USERNAME', server_config.get('sftp_username'))
            sftp_password = os.getenv('SFTP_PASSWORD', server_config.get('sftp_password'))
            
            if not all([sftp_host, sftp_username, sftp_password]):
                logger.warning("SFTP credentials not configured")
                return []
            
            # Connect to SFTP
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(sftp_host, port=sftp_port, username=sftp_username, password=sftp_password)
            
            sftp = ssh.open_sftp()
            
            # Navigate to deathlogs directory
            server_id = server_config.get('server_id', 'unknown')
            remote_path = f"./{sftp_host}_{server_id}/actual1/deathlogs/"
            
            all_lines = []
            
            try:
                # Get all CSV files recursively
                csv_files = []
                def scan_directory(path):
                    try:
                        for item in sftp.listdir_attr(path):
                            full_path = f"{path}/{item.filename}"
                            if stat.S_ISDIR(item.st_mode):
                                scan_directory(full_path)
                            elif item.filename.endswith('.csv'):
                                csv_files.append((full_path, item.st_mtime))
                    except FileNotFoundError:
                        logger.warning(f"Directory not found: {path}")
                
                scan_directory(remote_path)
                
                # Sort by modification time (chronological order)
                csv_files.sort(key=lambda x: x[1])
                
                # Download and read all files with proper decoding
                for filepath, _ in csv_files:
                    with sftp.open(filepath, 'r') as f:
                        file_content = f.read()
                        if isinstance(file_content, bytes):
                            file_content = file_content.decode('utf-8')
                        all_lines.extend(line.strip() for line in file_content.splitlines())
                    
            except FileNotFoundError:
                logger.warning(f"Deathlogs directory not found: {remote_path}")
            
            sftp.close()
            ssh.close()
            return all_lines
            
        except Exception as e:
            logger.error(f"Failed to fetch SFTP files for historical parsing: {e}")
            return []
    
    async def clear_server_data(self, guild_id: int, server_id: str):
        """Clear all PvP data for a server before historical refresh"""
        try:
            # Clear PvP stats
            await self.bot.db_manager.pvp_data.delete_many({
                "guild_id": guild_id,
                "server_id": server_id
            })
            
            # Clear kill events
            await self.bot.db_manager.kill_events.delete_many({
                "guild_id": guild_id,
                "server_id": server_id
            })
            
            logger.info(f"Cleared PvP data for server {server_id} in guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear server data: {e}")
    
    async def update_progress_embed(self, channel: discord.TextChannel, 
                                   embed_message: discord.Message,
                                   current: int, total: int, server_id: str):
        """Update progress embed every 30 seconds"""
        try:
            progress_percent = (current / total * 100) if total > 0 else 0
            progress_bar_length = 20
            filled_length = int(progress_bar_length * current // total) if total > 0 else 0
            progress_bar = '█' * filled_length + '░' * (progress_bar_length - filled_length)
            
            embed = discord.Embed(
                title="📊 Historical Data Refresh",
                description=f"Refreshing historical data for server **{server_id}**",
                color=0x00FF7F,  # Spring green
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(
                name="Progress",
                value=f"```{progress_bar}```\n{current:,} / {total:,} events ({progress_percent:.1f}%)",
                inline=False
            )
            
            embed.add_field(
                name="Status",
                value="🔄 Processing historical kill events...",
                inline=True
            )
            
            # Add thumbnail
            thumbnail_path = Path('./assets/main.png')
            if thumbnail_path.exists():
                embed.set_thumbnail(url="attachment://main.png")
            
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
            
            await embed_message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to update progress embed: {e}")
    
    async def complete_progress_embed(self, embed_message: discord.Message,
                                     server_id: str, processed_count: int, 
                                     duration_seconds: float):
        """Update embed when refresh is complete"""
        try:
            embed = discord.Embed(
                title="✅ Historical Data Refresh Complete",
                description=f"Successfully refreshed historical data for server **{server_id}**",
                color=0x00FF00,  # Green
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(
                name="📈 Results",
                value=f"**{processed_count:,}** kill events processed",
                inline=True
            )
            
            embed.add_field(
                name="⏱️ Duration", 
                value=f"{duration_seconds:.1f} seconds",
                inline=True
            )
            
            embed.add_field(
                name="🎯 Status",
                value="Ready for live killfeed tracking",
                inline=False
            )
            
            # Add thumbnail
            thumbnail_path = Path('./assets/main.png')
            if thumbnail_path.exists():
                embed.set_thumbnail(url="attachment://main.png")
            
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
            
            await embed_message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to complete progress embed: {e}")
    
    async def refresh_server_data(self, guild_id: int, server_config: Dict[str, Any], 
                                 channel: Optional[discord.TextChannel] = None):
        """Refresh historical data for a server"""
        try:
            server_id = server_config.get('server_id', 'unknown')
            refresh_key = f"{guild_id}_{server_id}"
            
            # Check if refresh is already running
            if self.active_refreshes.get(refresh_key, False):
                logger.warning(f"Refresh already running for server {server_id}")
                return False
            
            self.active_refreshes[refresh_key] = True
            start_time = datetime.now()
            
            logger.info(f"Starting historical refresh for server {server_id} in guild {guild_id}")
            
            # Send initial progress embed
            embed_message = None
            if channel:
                initial_embed = discord.Embed(
                    title="🚀 Starting Historical Refresh",
                    description=f"Initializing historical data refresh for server **{server_id}**",
                    color=0xFFD700,  # Gold
                    timestamp=datetime.now(timezone.utc)
                )
                initial_embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                embed_message = await channel.send(embed=initial_embed)
            
            # Clear existing data
            await self.clear_server_data(guild_id, server_id)
            
            # Get all CSV files
            lines = await self.get_all_csv_files(server_config)
            
            if not lines:
                logger.warning(f"No historical data found for server {server_id}")
                self.active_refreshes[refresh_key] = False
                return False
            
            total_lines = len(lines)
            processed_count = 0
            last_update_time = datetime.now()
            
            # Process each line
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                
                # Parse kill event (but don't send embeds)
                kill_data = await self.killfeed_parser.parse_csv_line(line)
                if kill_data:
                    # Add to database without sending embeds
                    await self.bot.db_manager.add_kill_event(guild_id, server_id, kill_data)
                    
                    # Update stats
                    if not kill_data['is_suicide']:
                        await self.bot.db_manager.update_pvp_stats(
                            guild_id, server_id, kill_data['killer'], 
                            {"$inc": {"kills": 1}}
                        )
                    
                    await self.bot.db_manager.update_pvp_stats(
                        guild_id, server_id, kill_data['victim'],
                        {"$inc": {"deaths" if not kill_data['is_suicide'] else "suicides": 1}}
                    )
                    
                    processed_count += 1
                
                # Update progress embed every 30 seconds
                current_time = datetime.now()
                if embed_message and (current_time - last_update_time).total_seconds() >= 30:
                    await self.update_progress_embed(channel, embed_message, i + 1, total_lines, server_id)
                    last_update_time = current_time
            
            # Complete the refresh
            duration = (datetime.now() - start_time).total_seconds()
            
            if embed_message:
                await self.complete_progress_embed(embed_message, server_id, processed_count, duration)
            
            logger.info(f"Historical refresh completed for server {server_id}: {processed_count} events in {duration:.1f}s")
            
            self.active_refreshes[refresh_key] = False
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh server data: {e}")
            if refresh_key in self.active_refreshes:
                self.active_refreshes[refresh_key] = False
            return False
    
    async def auto_refresh_after_server_add(self, guild_id: int, server_config: Dict[str, Any]):
        """Automatically refresh data 30 seconds after server is added"""
        try:
            await asyncio.sleep(30)  # Wait 30 seconds
            await self.refresh_server_data(guild_id, server_config)
            
        except Exception as e:
            logger.error(f"Failed to auto-refresh after server add: {e}")