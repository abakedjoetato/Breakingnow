#!/usr/bin/env python3
"""
Emerald's Killfeed - Discord Bot for Deadside PvP Engine
Full production-grade bot with killfeed parsing, stats, economy, and premium features
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.models.database import DatabaseManager
from bot.parsers.killfeed_parser import KillfeedParser
from bot.parsers.historical_parser import HistoricalParser
from bot.parsers.log_parser import LogParser

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class EmeraldKillfeedBot(commands.Bot):
    """Main bot class for Emerald's Killfeed"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            status=discord.Status.online,
            activity=discord.Game(name="Emerald's Killfeed v2.0")
        )
        
        # Initialize variables
        self.database = None
        self.scheduler = AsyncIOScheduler()
        self.killfeed_parser = None
        self.log_parser = None
        self.historical_parser = None
        self.ssh_connections = []
        
        # Missing essential properties
        self.assets_path = Path('./assets')
        self.dev_data_path = Path('./dev_data')
        self.dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'
        
        logger.info("Bot initialized in production mode")
    

    
    async def load_cogs(self):
        """Load all bot cogs"""
        try:
            # Load cogs in order
            cogs = [
                'bot.cogs.core',
                'bot.cogs.economy',
                'bot.cogs.gambling', 
                'bot.cogs.linking',
                'bot.cogs.stats',
                'bot.cogs.bounties',
                'bot.cogs.factions',
                'bot.cogs.premium',
                'bot.cogs.leaderboards',
                'bot.cogs.admin_channels',
                'bot.cogs.embed_test'
            ]
            
            loaded_cogs = []
            failed_cogs = []
            
            for cog in cogs:
                try:
                    self.load_extension(cog)
                    loaded_cogs.append(cog)
                    logger.info(f"✅ Successfully loaded cog: {cog}")
                except Exception as e:
                    failed_cogs.append(cog)
                    logger.error(f"❌ Failed to load cog {cog}: {e}")
            
            # Verify commands are registered
            try:
                command_count = len(self.pending_application_commands) if hasattr(self, 'pending_application_commands') else 0
                logger.info(f"📊 Loaded {len(loaded_cogs)}/{len(cogs)} cogs successfully")
                logger.info(f"📊 Total slash commands registered: {command_count}")
                
                # Debug: List actual commands found
                if command_count > 0:
                    command_names = [cmd.name for cmd in self.pending_application_commands]
                    logger.info(f"🔍 Commands found: {', '.join(command_names)}")
                else:
                    logger.info("ℹ️ Commands will be synced after connection")
            except Exception as e:
                logger.warning(f"Command count check failed: {e}")
            
            if failed_cogs:
                logger.error(f"❌ Failed cogs: {failed_cogs}")
                return False
            else:
                logger.info("✅ All cogs loaded and commands registered successfully")
                return True
            
        except Exception as e:
            logger.error(f"❌ Critical failure loading cogs: {e}")
            return False
    
    async def cleanup_connections(self):
        """Clean up AsyncSSH connections on shutdown"""
        try:
            if hasattr(self, 'killfeed_parser') and self.killfeed_parser:
                await self.killfeed_parser.cleanup_sftp_connections()
                
            if hasattr(self, 'log_parser') and self.log_parser:
                # Clean up log parser SFTP connections
                for pool_key, conn in list(self.log_parser.sftp_pool.items()):
                    try:
                        conn.close()
                    except:
                        pass
                self.log_parser.sftp_pool.clear()
                
            logger.info("Cleaned up all SFTP connections")
            
        except Exception as e:
            logger.error(f"Failed to cleanup connections: {e}")
    
    async def setup_database(self):
        """Setup MongoDB connection"""
        mongo_uri = os.getenv('MONGO_URI')
        if not mongo_uri:
            logger.error("MONGO_URI not found in environment variables")
            return False
            
        try:
            self.mongo_client = AsyncIOMotorClient(mongo_uri)
            self.database = self.mongo_client.emerald_killfeed
            
            # Initialize database manager with PHASE 1 architecture
            self.db_manager = DatabaseManager(self.mongo_client)
            
            # Test connection
            await self.mongo_client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            # Initialize database indexes
            await self.db_manager.initialize_indexes()
            logger.info("Database architecture initialized (PHASE 1)")
            
            # Initialize parsers (PHASE 2)
            self.killfeed_parser = KillfeedParser(self)
            self.historical_parser = HistoricalParser(self)
            self.log_parser = LogParser(self)
            logger.info("Parsers initialized (PHASE 2)")
            
            return True
            
        except Exception as e:
            logger.error("Failed to connect to MongoDB: %s", e)
            return False
    
    def setup_scheduler(self):
        """Setup background job scheduler"""
        try:
            self.scheduler.start()
            logger.info("Background job scheduler started")
            return True
        except Exception as e:
            logger.error("Failed to start scheduler: %s", e)
            return False
    

    
    async def on_ready(self):
        """Called when bot is ready and connected to Discord - RATE LIMIT SAFE VERSION"""
        # Only run setup once
        if hasattr(self, '_setup_complete'):
            return
        
        logger.info("🚀 Bot is ready! Loading cogs first...")
        
        # CRITICAL: Load cogs FIRST before anything else
        try:
            logger.info("🔧 Loading cogs for command registration...")
            cogs_success = await self.load_cogs()
            logger.info(f"🎯 Cog loading: {'✅ Complete' if cogs_success else '❌ Failed'}")
            
            # Give py-cord time to process async setup functions
            await asyncio.sleep(0.5)  # Allow py-cord to process command registration
            
            # Now manually sync commands to ensure they're registered
            try:
                await self.sync_commands()
                logger.info("🔄 Command sync completed")
            except Exception as sync_error:
                logger.warning(f"⚠️ Command sync failed: {sync_error}")
            
            # Commands are now registered
            command_count = len(self.pending_application_commands) if hasattr(self, 'pending_application_commands') else 0
            logger.info(f"📊 {command_count} commands registered locally")
            
            # Debug: List actual commands if any
            if command_count > 0:
                command_names = [cmd.name for cmd in self.pending_application_commands]
                logger.info(f"🔍 Commands found: {', '.join(command_names[:5])}{'...' if len(command_names) > 5 else ''}")
            else:
                logger.warning("⚠️ No commands registered - this may indicate a cog loading issue")
            
        except Exception as e:
            logger.error(f"❌ Critical error loading cogs: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info("🚀 Now starting database and parser setup...")
        
        try:
            # Connect to MongoDB
            db_success = await self.setup_database()
            logger.info(f"📊 Database setup: {'✅ Success' if db_success else '❌ Failed'}")
            
            # Start scheduler
            scheduler_success = self.setup_scheduler()
            logger.info(f"⏰ Scheduler setup: {'✅ Success' if scheduler_success else '❌ Failed'}")
            
            # Schedule parsers (PHASE 2)
            if self.killfeed_parser:
                self.killfeed_parser.schedule_killfeed_parser()
                logger.info("📡 Killfeed parser scheduled")
            if self.log_parser:
                self.log_parser.schedule_log_parser()
                logger.info("📜 Log parser scheduled")
            
            # RATE LIMIT SAFE COMMAND SYNC - USE GUILD-SPECIFIC SYNC ONLY
            command_count = len(self.pending_application_commands) if hasattr(self, 'pending_application_commands') else 0
            logger.info(f"📊 {command_count} commands loaded, checking sync status...")
            
            if command_count > 0:
                logger.info("🔄 Implementing RATE LIMIT SAFE sync strategy...")
                
                sync_needed = False
                
                try:
                    # Check if commands exist in the primary guild only (avoid rate limits)
                    if self.guilds:
                        primary_guild = self.guilds[0]
                        # Use HTTP API directly to check existing commands
                        existing_commands = await self.http.get_guild_commands(self.application_id, primary_guild.id)
                        
                        if len(existing_commands) == 0:
                            sync_needed = True
                            logger.info(f"🔄 No commands found in {primary_guild.name} - sync required")
                        else:
                            logger.info(f"✅ Found {len(existing_commands)} commands in {primary_guild.name} - no sync needed")
                            
                except Exception as check_error:
                    logger.info(f"Could not check existing commands, assuming sync needed: {check_error}")
                    sync_needed = True
                
                if sync_needed:
                    try:
                        # Try global sync first
                        logger.info("Attempting global command sync...")
                        await self.sync_commands()
                        logger.info("✅ Global command sync successful")
                    except Exception as global_sync_error:
                        logger.warning(f"Global sync failed, falling back to per-guild: {global_sync_error}")
                        
                        # Fall back to guild-specific sync
                        for guild in self.guilds:
                            try:
                                synced = await self.sync_commands(guild_ids=[guild.id])
                                if synced:
                                    logger.info(f"✅ Synced {len(synced)} commands to {guild.name}")
                                else:
                                    logger.info(f"✅ Synced commands to {guild.name} (count unavailable)")
                                await asyncio.sleep(1)  # Rate limit protection
                            except Exception as guild_sync_error:
                                logger.error(f"Failed to sync to {guild.name}: {guild_sync_error}")
                                continue
                        
                        logger.info("🎉 Guild fallback sync completed")
                else:
                    logger.info("✅ Commands already synced - skipping to avoid rate limits")
            
            # Bot ready messages
            if self.user:
                logger.info("✅ Bot logged in as %s (ID: %s)", self.user.name, self.user.id)
            logger.info("✅ Connected to %d guilds", len(self.guilds))
            
            for guild in self.guilds:
                logger.info(f"📡 Bot connected to: {guild.name} (ID: {guild.id})")
            
            # Verify assets exist
            if self.assets_path.exists():
                assets = list(self.assets_path.glob('*.png'))
                logger.info("📁 Found %d asset files", len(assets))
            else:
                logger.warning("⚠️ Assets directory not found")
            
            # Verify dev data exists (for testing)
            if self.dev_mode:
                csv_files = list(self.dev_data_path.glob('csv/*.csv'))
                log_files = list(self.dev_data_path.glob('logs/*.log'))
                logger.info("🧪 Dev mode: Found %d CSV files and %d log files", len(csv_files), len(log_files))
            
            logger.info("🎉 Bot setup completed successfully!")
            self._setup_complete = True
            
        except Exception as e:
            logger.error(f"❌ Critical error in bot setup: {e}")
            raise
    
    async def on_guild_join(self, guild):
        """Called when bot joins a new guild"""
        logger.info("Joined guild: %s (ID: %s)", guild.name, guild.id)
        
        # Initialize guild in database (will be implemented in Phase 1)
        # await self.database.guilds.insert_one({
        #     'guild_id': guild.id,
        #     'guild_name': guild.name,
        #     'created_at': datetime.utcnow(),
        #     'premium_servers': [],
        #     'channels': {}
        # })
    
    async def on_guild_remove(self, guild):
        """Called when bot is removed from a guild"""
        logger.info("Left guild: %s (ID: %s)", guild.name, guild.id)
    
    async def close(self):
        """Clean shutdown"""
        logger.info("Shutting down bot...")
        
        # Clean up SFTP connections
        await self.cleanup_connections()
        
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
        
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB connection closed")
        
        await super().close()
        logger.info("Bot shutdown complete")

async def main():
    """Main entry point"""
    # Check required environment variables
    bot_token = os.getenv('BOT_TOKEN')
    mongo_uri = os.getenv('MONGO_URI')
    
    if not bot_token:
        logger.error("BOT_TOKEN not found in environment variables")
        logger.error("Please set your Discord bot token in the .env file")
        return
    
    if not mongo_uri:
        logger.error("MONGO_URI not found in environment variables")
        logger.error("Please set your MongoDB connection string in the .env file")
        return
    
    # Create and run bot
    bot = EmeraldKillfeedBot()
    
    try:
        await bot.start(bot_token)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error("An error occurred: %s", e)
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())