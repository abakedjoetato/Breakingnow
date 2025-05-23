"""
Emerald's Killfeed - Premium Management System (PHASE 9)
/sethome by BOT_OWNER_ID
/premium assign, /premium revoke, /premium status
Premium is assigned per server, not user
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

class Premium(commands.Cog):
    """
    PREMIUM MGMT (PHASE 9)
    - /sethome by BOT_OWNER_ID
    - /premium assign, /premium revoke, /premium status
    - Premium is assigned per server, not user
    """

    def __init__(self, bot):
        self.bot = bot
        self.bot_owner_id = int(os.getenv('BOT_OWNER_ID', 0))

    def is_bot_owner(self, user_id: int) -> bool:
        """Check if user is the bot owner"""
        import os
        bot_owner_id = int(os.getenv('BOT_OWNER_ID', 0))
        return user_id == bot_owner_id

    @commands.slash_command(name="sethome", description="Set this server as the bot's home server")
    async def sethome(self, ctx: discord.ApplicationContext):
        """Set this server as the bot's home server (BOT_OWNER_ID only)"""
        try:
            # Check if user is bot owner
            if not self.is_bot_owner(ctx.user.id):
                await ctx.respond("❌ Only the bot owner can use this command!", ephemeral=True)
                return

            guild_id = ctx.guild.id

            # Update or create guild as home server
            await self.bot.db_manager.guilds.update_one(
                {"guild_id": guild_id},
                {
                    "$set": {
                        "guild_name": ctx.guild.name,
                        "is_home_server": True,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(timezone.utc),
                        "servers": [],
                        "channels": {}
                    }
                },
                upsert=True
            )

            # Remove home server status from other guilds
            await self.bot.db_manager.guilds.update_many(
                {"guild_id": {"$ne": guild_id}},
                {"$unset": {"is_home_server": ""}}
            )

            embed = discord.Embed(
                title="🏠 Home Server Set",
                description=f"**{ctx.guild.name}** has been set as the bot's home server!",
                color=0x00FF00,
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="🎯 Benefits",
                value="• Full access to all premium features\n• Administrative controls\n• Premium management commands",
                inline=False
            )

            embed.set_thumbnail(url="attachment://main.png")
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Failed to set home server: {e}")
            await ctx.respond("❌ Failed to set home server.", ephemeral=True)

    premium = discord.SlashCommandGroup("premium", "Premium management commands")

    @premium.command(name="assign", description="Assign premium to a server")
    @commands.has_permissions(administrator=True)
    async def premium_assign(self, ctx: discord.ApplicationContext, 
                           server_id: str, duration_days: int = 30):
        """Assign premium status to a server"""
        try:
            guild_id = ctx.guild.id

            # Check if user is bot owner or in home server
            is_owner = self.is_bot_owner(ctx.user.id)

            # Check if current guild is home server
            home_guild = await self.bot.db_manager.guilds.find_one({
                "guild_id": guild_id,
                "is_home_server": True
            })

            if not is_owner and not home_guild:
                await ctx.respond("❌ Premium management is only available to bot owners or in the home server!", ephemeral=True)
                return

            # Validate duration
            if duration_days <= 0 or duration_days > 365:
                await ctx.respond("❌ Duration must be between 1 and 365 days!", ephemeral=True)
                return

            # Calculate expiration date
            expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)

            # Set premium status
            success = await self.bot.db_manager.set_premium_status(guild_id, server_id, expires_at)

            if success:
                embed = discord.Embed(
                    title="⭐ Premium Assigned",
                    description=f"Premium status assigned to server **{server_id}**!",
                    color=0xFFD700,
                    timestamp=datetime.now(timezone.utc)
                )

                embed.add_field(
                    name="⏰ Duration",
                    value=f"{duration_days} days",
                    inline=True
                )

                embed.add_field(
                    name="📅 Expires",
                    value=f"<t:{int(expires_at.timestamp())}:F>",
                    inline=True
                )

                embed.add_field(
                    name="🎯 Features Unlocked",
                    value="• Economy System\n• Gambling Games\n• Bounty System\n• Faction System\n• Log Parser\n• Leaderboards",
                    inline=False
                )

                embed.set_thumbnail(url="attachment://main.png")
                embed.set_footer(text="Powered by Discord.gg/EmeraldServers")

                await ctx.respond(embed=embed)
            else:
                await ctx.respond("❌ Failed to assign premium status.", ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to assign premium: {e}")
            await ctx.respond("❌ Failed to assign premium.", ephemeral=True)

    @premium.command(name="revoke", description="Revoke premium from a server")
    @commands.has_permissions(administrator=True)
    async def premium_revoke(self, ctx: discord.ApplicationContext, server_id: str):
        """Revoke premium status from a server"""
        try:
            guild_id = ctx.guild.id

            # Check if user is bot owner or in home server
            is_owner = self.is_bot_owner(ctx.user.id)

            # Check if current guild is home server
            home_guild = await self.bot.db_manager.guilds.find_one({
                "guild_id": guild_id,
                "is_home_server": True
            })

            if not is_owner and not home_guild:
                await ctx.respond("❌ Premium management is only available to bot owners or in the home server!", ephemeral=True)
                return

            # Check if server has premium
            is_premium = await self.bot.db_manager.is_premium_server(guild_id, server_id)

            if not is_premium:
                await ctx.respond(f"❌ Server **{server_id}** does not have premium status!", ephemeral=True)
                return

            # Revoke premium
            success = await self.bot.db_manager.set_premium_status(guild_id, server_id, None)

            if success:
                embed = discord.Embed(
                    title="❌ Premium Revoked",
                    description=f"Premium status revoked from server **{server_id}**.",
                    color=0xFF6B6B,
                    timestamp=datetime.now(timezone.utc)
                )

                embed.add_field(
                    name="⚠️ Note",
                    value="Premium features are now disabled for this server.",
                    inline=False
                )

                embed.set_thumbnail(url="attachment://main.png")
                embed.set_footer(text="Powered by Discord.gg/EmeraldServers")

                await ctx.respond(embed=embed)
            else:
                await ctx.respond("❌ Failed to revoke premium status.", ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to revoke premium: {e}")
            await ctx.respond("❌ Failed to revoke premium.", ephemeral=True)

    @premium.command(name="status", description="Check premium status for servers")
    async def premium_status(self, ctx: discord.ApplicationContext):
        """Check premium status for all servers in the guild"""
        try:
            guild_id = ctx.guild.id

            # Get guild configuration
            guild_config = await self.bot.db_manager.get_guild(guild_id)

            if not guild_config:
                await ctx.respond("❌ This guild is not configured!", ephemeral=True)
                return

            servers = guild_config.get('servers', [])

            if not servers:
                embed = discord.Embed(
                    title="⭐ Premium Status",
                    description="No game servers configured for this guild.",
                    color=0x808080,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(
                    name="🎯 Next Steps",
                    value="Use `/server add` to add game servers first.",
                    inline=False
                )
                embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                await ctx.respond(embed=embed)
                return

            # Check premium status for each server
            premium_servers = []
            free_servers = []

            for server_config in servers:
                server_id = server_config.get('server_id', 'unknown')
                is_premium = await self.bot.db_manager.is_premium_server(guild_id, server_id)

                if is_premium:
                    # Get expiration info
                    premium_doc = await self.bot.db_manager.premium.find_one({
                        "guild_id": guild_id,
                        "server_id": server_id
                    })

                    if premium_doc and premium_doc.get('expires_at'):
                        expires_text = f"<t:{int(premium_doc['expires_at'].timestamp())}:R>"
                    else:
                        expires_text = "Never"

                    premium_servers.append(f"**{server_id}** - Expires {expires_text}")
                else:
                    free_servers.append(f"**{server_id}** - Free tier")

            # Create status embed
            embed = discord.Embed(
                title="⭐ Premium Status",
                description=f"Premium status for **{ctx.guild.name}**",
                color=0xFFD700 if premium_servers else 0x808080,
                timestamp=datetime.now(timezone.utc)
            )

            if premium_servers:
                embed.add_field(
                    name="✅ Premium Servers",
                    value="\n".join(premium_servers),
                    inline=False
                )

            if free_servers:
                embed.add_field(
                    name="🆓 Free Servers",
                    value="\n".join(free_servers),
                    inline=False
                )

            # Check if user can manage premium
            is_owner = self.is_bot_owner(ctx.user.id)
            home_guild = await self.bot.db_manager.guilds.find_one({
                "guild_id": guild_id,
                "is_home_server": True
            })

            if is_owner or home_guild:
                embed.add_field(
                    name="🛠️ Management",
                    value="Use `/premium assign` and `/premium revoke` to manage premium status.",
                    inline=False
                )

            embed.set_thumbnail(url="attachment://main.png")
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Failed to check premium status: {e}")
            await ctx.respond("❌ Failed to check premium status.", ephemeral=True)

    server = discord.SlashCommandGroup("server", "Game server management commands")

    @server.command(name="add", description="Add a game server with SFTP credentials to this guild")
    @commands.has_permissions(administrator=True)
    async def server_add(self, ctx: discord.ApplicationContext, 
                        name: str, host: str, port: int, username: str, password: str, serverid: str):
        """Add a game server with full SFTP credentials to the guild"""
        try:
            guild_id = ctx.guild.id

            # Validate inputs
            serverid = serverid.strip()
            name = name.strip()
            host = host.strip()
            username = username.strip()
            password = password.strip()

            if not all([serverid, name, host, username, password]):
                await ctx.respond("❌ All fields are required: name, host, port, username, password, serverid", ephemeral=True)
                return

            if not (1 <= port <= 65535):
                await ctx.respond("❌ Port must be between 1 and 65535", ephemeral=True)
                return

            # Get or create guild
            guild_config = await self.bot.db_manager.get_guild(guild_id)
            if not guild_config:
                guild_config = await self.bot.db_manager.create_guild(guild_id, ctx.guild.name)

            # Check if server already exists
            existing_servers = guild_config.get('servers', [])
            for server in existing_servers:
                if server.get('server_id') == serverid:
                    await ctx.respond(f"❌ Server **{serverid}** is already added!", ephemeral=True)
                    return

            # Create server config with full SFTP credentials
            server_config = {
                'server_id': serverid,
                'server_name': name,
                'sftp_host': host,
                'sftp_port': port,
                'sftp_username': username,
                'sftp_password': password,
                'added_at': datetime.now(timezone.utc),
                'added_by': ctx.user.id
            }

            # Add server to guild
            success = await self.bot.db_manager.add_server_to_guild(guild_id, server_config)

            if success:
                embed = discord.Embed(
                    title="🖥️ Server Added",
                    description=f"Game server **{server_config['server_name']}** has been added!",
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc)
                )

                embed.add_field(
                    name="🆔 Server ID",
                    value=serverid,
                    inline=True
                )

                embed.add_field(
                    name="🌐 SFTP Host",
                    value=f"{host}:{port}",
                    inline=True
                )

                embed.add_field(
                    name="👤 Added by",
                    value=ctx.user.mention,
                    inline=True
                )

                embed.add_field(
                    name="⏰ Historical Refresh",
                    value="Starting in 30 seconds...",
                    inline=False
                )

                embed.add_field(
                    name="🎯 Features Available",
                    value="• Killfeed parsing (FREE)\n• Historical data refresh (FREE)\n• Premium features (requires subscription)",
                    inline=False
                )

                embed.set_thumbnail(url="attachment://main.png")
                embed.set_footer(text="Powered by Discord.gg/EmeraldServers")

                await ctx.respond(embed=embed)

                # Trigger automatic historical refresh after 30 seconds
                if self.bot.historical_parser:
                    import asyncio
                    asyncio.create_task(
                        self.bot.historical_parser.auto_refresh_after_server_add(guild_id, server_config)
                    )
            else:
                await ctx.respond("❌ Failed to add server.", ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to add server: {e}")
            await ctx.respond("❌ Failed to add server.", ephemeral=True)

    @server.command(name="remove", description="Remove a game server from this guild")
    @commands.has_permissions(administrator=True)
    async def server_remove(self, ctx: discord.ApplicationContext, 
                           server_name: str):
        """Remove a game server from the guild"""
        try:
            if not ctx.guild:
                await ctx.respond("❌ This command can only be used in a server!", ephemeral=True)
                return

            guild_id = ctx.guild.id
            server_name = server_name.strip()

            if not server_name:
                await ctx.respond("❌ Server name cannot be empty!", ephemeral=True)
                return

            # Get guild configuration
            guild_config = await self.bot.db_manager.get_guild(guild_id)
            if not guild_config:
                await ctx.respond("❌ No servers configured for this guild!", ephemeral=True)
                return

            # Find the server to remove by name
            servers = guild_config.get('servers', [])
            server_to_remove = None
            updated_servers = []

            for server in servers:
                if server.get('server_name') == server_name:
                    server_to_remove = server
                else:
                    updated_servers.append(server)

            if not server_to_remove:
                await ctx.respond(f"❌ Server **{server_name}** not found!", ephemeral=True)
                return

            # Update guild configuration with remaining servers
            result = await self.bot.db_manager.guilds.update_one(
                {"guild_id": guild_id},
                {"$set": {"servers": updated_servers}}
            )

            if result.modified_count > 0:
                # Also clear all PvP data for this server
                server_id = server_to_remove.get('server_id')
                if server_id:
                    # Clear PvP data directly from the collections
                    await self.bot.db_manager.pvp_events.delete_many({
                        "guild_id": guild_id,
                        "server_id": server_id
                    })
                    await self.bot.db_manager.player_stats.delete_many({
                        "guild_id": guild_id,
                        "server_id": server_id
                    })

                embed = discord.Embed(
                    title="🗑️ Server Removed",
                    description=f"Game server **{server_name}** has been removed!",
                    color=0xFF6B6B,
                    timestamp=datetime.now(timezone.utc)
                )

                embed.add_field(
                    name="🆔 Server ID",
                    value=server_to_remove.get('server_id', 'N/A'),
                    inline=True
                )

                embed.add_field(
                    name="👤 Removed by",
                    value=ctx.user.mention,
                    inline=True
                )

                embed.add_field(
                    name="🧹 Data Cleanup",
                    value="All PvP data for this server has been cleared",
                    inline=False
                )

                embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("❌ Failed to remove server.", ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to remove server: {e}")
            await ctx.respond("❌ Failed to remove server.", ephemeral=True)

    @server.command(name="list", description="List all game servers for this guild")
    async def server_list(self, ctx: discord.ApplicationContext):
        """List all game servers configured for the guild"""
        try:
            # Defer the response since this might take a while
            await ctx.defer()
            guild_id = ctx.guild.id

            # Get guild configuration
            guild_config = await self.bot.db_manager.get_guild(guild_id)

            if not guild_config:
                embed = discord.Embed(
                    title="🖥️ Game Servers",
                    description="No servers configured for this guild.",
                    color=0x808080,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(
                    name="🎯 Get Started",
                    value="Use `/server add` to add your first server!",
                    inline=False
                )
                embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                await ctx.respond(embed=embed)
                return

            servers = guild_config.get('servers', [])

            if not servers:
                embed = discord.Embed(
                    title="🖥️ Game Servers",
                    description="No servers configured for this guild.",
                    color=0x808080,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(
                    name="🎯 Get Started",
                    value="Use `/server add` to add your first server!",
                    inline=False
                )
                embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                await ctx.respond(embed=embed)
                return

            # Create server list embed
            embed = discord.Embed(
                title="🖥️ Game Servers",
                description=f"**{len(servers)}** servers configured",
                color=0x3498DB,
                timestamp=datetime.now(timezone.utc)
            )

            server_list = []
            for i, server in enumerate(servers, 1):
                server_id = server.get('server_id', 'Unknown')
                server_name = server.get('server_name', server_id)

                # Check premium status
                is_premium = await self.bot.db_manager.is_premium_server(guild_id, server_id)
                status = "⭐ Premium" if is_premium else "🆓 Free"

                server_list.append(f"**{i}.** {server_name} ({server_id})\n    {status}")

            embed.add_field(
                name="📋 Server List",
                value="\n".join(server_list),
                inline=False
            )

            embed.set_thumbnail(url="attachment://main.png")
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Failed to list servers: {e}")
            await ctx.respond("❌ Failed to list servers.", ephemeral=True)

    @server.command(name="refresh", description="Refresh historical data for a server")
    @commands.has_permissions(administrator=True)
    async def server_refresh(self, ctx: discord.ApplicationContext, server_id: str):
        """Manually refresh historical data for a server"""
        try:
            guild_id = ctx.guild.id

            # Get guild configuration
            guild_config = await self.bot.db_manager.get_guild(guild_id)
            if not guild_config:
                await ctx.respond("❌ This guild is not configured!", ephemeral=True)
                return

            # Find the server
            server_config = None
            for server in guild_config.get('servers', []):
                if server.get('server_id') == server_id:
                    server_config = server
                    break

            if not server_config:
                await ctx.respond(f"❌ Server **{server_id}** not found!", ephemeral=True)
                return

            # Start historical refresh
            if self.bot.historical_parser:
                await ctx.respond("🔄 Starting historical data refresh...")

                success = await self.bot.historical_parser.refresh_server_data(
                    guild_id, server_config, ctx.channel
                )

                if not success:
                    await ctx.followup.send("❌ Historical refresh failed. Please check the logs.")
            else:
                await ctx.respond("❌ Historical parser not available.", ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to refresh server: {e}")
            await ctx.respond("❌ Failed to refresh server data.", ephemeral=True)

def setup(bot):
    bot.add_cog(Premium(bot))