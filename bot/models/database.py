"""
Emerald's Killfeed - Database Models and Architecture
Implements PHASE 1 data architecture requirements
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Database manager implementing PHASE 1 architecture:
    - All PvP data stored per game server
    - Linking, wallet, factions stored per guild
    - Players linked to one account spanning all servers in guild
    - Premium tracked per game server, not user or guild
    """
    
    def __init__(self, mongo_client: AsyncIOMotorClient):
        self.client = mongo_client
        self.db: AsyncIOMotorDatabase = mongo_client.emerald_killfeed
        
        # Collections based on PHASE 1 architecture
        self.guilds = self.db.guilds                    # Guild configurations
        self.players = self.db.players                  # Player linking (per guild)
        self.pvp_data = self.db.pvp_data               # PvP stats (per server)
        self.economy = self.db.economy                  # Wallets (per guild)
        self.factions = self.db.factions               # Factions (per guild)
        self.premium = self.db.premium                  # Premium status (per server)
        self.kill_events = self.db.kill_events         # Kill events (per server)
        self.bounties = self.db.bounties               # Bounties (per guild)
        self.leaderboards = self.db.leaderboards       # Leaderboard configs
        
    async def initialize_indexes(self):
        """Create database indexes for optimal performance"""
        try:
            # Guild indexes
            await self.guilds.create_index("guild_id", unique=True)
            
            # Player indexes (guild-scoped)
            await self.players.create_index([("guild_id", 1), ("discord_id", 1)], unique=True)
            await self.players.create_index([("guild_id", 1), ("linked_characters", 1)])
            
            # PvP data indexes (server-scoped)
            await self.pvp_data.create_index([("guild_id", 1), ("server_id", 1), ("player_name", 1)], unique=True)
            await self.pvp_data.create_index([("guild_id", 1), ("server_id", 1), ("kills", -1)])
            await self.pvp_data.create_index([("guild_id", 1), ("server_id", 1), ("kdr", -1)])
            
            # Kill events indexes (server-scoped)
            await self.kill_events.create_index([("guild_id", 1), ("server_id", 1), ("timestamp", -1)])
            await self.kill_events.create_index([("guild_id", 1), ("server_id", 1), ("killer", 1)])
            await self.kill_events.create_index([("guild_id", 1), ("server_id", 1), ("victim", 1)])
            
            # Economy indexes (guild-scoped)
            await self.economy.create_index([("guild_id", 1), ("discord_id", 1)], unique=True)
            
            # Faction indexes (guild-scoped)
            await self.factions.create_index([("guild_id", 1), ("faction_name", 1)], unique=True)
            
            # Premium indexes (server-scoped)
            await self.premium.create_index([("guild_id", 1), ("server_id", 1)], unique=True)
            await self.premium.create_index("expires_at")
            
            # Bounty indexes (guild-scoped)
            await self.bounties.create_index([("guild_id", 1), ("target_player", 1)])
            await self.bounties.create_index("expires_at")
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create database indexes: {e}")
    
    # GUILD MANAGEMENT
    async def create_guild(self, guild_id: int, guild_name: str) -> Dict[str, Any]:
        """Create guild configuration"""
        guild_doc = {
            "guild_id": guild_id,
            "guild_name": guild_name,
            "created_at": datetime.now(timezone.utc),
            "servers": [],  # List of connected game servers
            "channels": {
                "killfeed": None,
                "leaderboard": None,
                "logs": None
            },
            "settings": {
                "prefix": "!",
                "timezone": "UTC"
            }
        }
        
        await self.guilds.insert_one(guild_doc)
        logger.info(f"Created guild: {guild_name} ({guild_id})")
        return guild_doc
    
    async def get_guild(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get guild configuration"""
        return await self.guilds.find_one({"guild_id": guild_id})
    
    async def add_server_to_guild(self, guild_id: int, server_config: Dict[str, Any]) -> bool:
        """Add game server to guild"""
        try:
            result = await self.guilds.update_one(
                {"guild_id": guild_id},
                {"$addToSet": {"servers": server_config}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to add server to guild {guild_id}: {e}")
            return False
    
    # PLAYER LINKING (Guild-scoped)
    async def link_player(self, guild_id: int, discord_id: int, character_name: str) -> bool:
        """Link Discord user to character (guild-scoped)"""
        try:
            player_doc = {
                "guild_id": guild_id,
                "discord_id": discord_id,
                "linked_characters": [character_name],
                "primary_character": character_name,
                "linked_at": datetime.now(timezone.utc)
            }
            
            await self.players.update_one(
                {"guild_id": guild_id, "discord_id": discord_id},
                {"$setOnInsert": player_doc, "$addToSet": {"linked_characters": character_name}},
                upsert=True
            )
            
            logger.info(f"Linked player {character_name} to Discord {discord_id} in guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to link player: {e}")
            return False
    
    async def get_linked_player(self, guild_id: int, discord_id: int) -> Optional[Dict[str, Any]]:
        """Get linked player data"""
        return await self.players.find_one({"guild_id": guild_id, "discord_id": discord_id})
    
    # PVP DATA (Server-scoped)
    async def update_pvp_stats(self, guild_id: int, server_id: str, player_name: str, 
                              stats_update: Dict[str, Any]) -> bool:
        """Update PvP statistics for player on specific server"""
        try:
            # Initialize default stats (without last_updated to avoid conflicts)
            default_stats = {
                "guild_id": guild_id,
                "server_id": server_id,
                "player_name": player_name,
                "kills": 0,
                "deaths": 0,
                "suicides": 0,
                "kdr": 0.0,
                "longest_streak": 0,
                "current_streak": 0,
                "favorite_weapon": None,
                "total_distance": 0.0,
                "created_at": datetime.now(timezone.utc)
            }
            
            # Calculate KDR
            if "kills" in stats_update or "deaths" in stats_update:
                current_doc = await self.pvp_data.find_one({
                    "guild_id": guild_id,
                    "server_id": server_id,
                    "player_name": player_name
                })
                
                kills = stats_update.get("kills", current_doc["kills"] if current_doc else 0)
                deaths = stats_update.get("deaths", current_doc["deaths"] if current_doc else 0)
                stats_update["kdr"] = kills / max(deaths, 1)
            
            stats_update["last_updated"] = datetime.now(timezone.utc)
            
            await self.pvp_data.update_one(
                {"guild_id": guild_id, "server_id": server_id, "player_name": player_name},
                {"$setOnInsert": default_stats, "$set": stats_update},
                upsert=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update PvP stats: {e}")
            return False
    
    async def get_pvp_stats(self, guild_id: int, server_id: str, player_name: str) -> Optional[Dict[str, Any]]:
        """Get PvP statistics for player on specific server"""
        return await self.pvp_data.find_one({
            "guild_id": guild_id,
            "server_id": server_id,
            "player_name": player_name
        })
    
    # KILL EVENTS (Server-scoped)
    async def add_kill_event(self, guild_id: int, server_id: str, kill_data: Dict[str, Any]) -> bool:
        """Add kill event to database"""
        try:
            kill_event = {
                "guild_id": guild_id,
                "server_id": server_id,
                "timestamp": datetime.now(timezone.utc),
                **kill_data
            }
            
            await self.kill_events.insert_one(kill_event)
            return True
            
        except Exception as e:
            logger.error(f"Failed to add kill event: {e}")
            return False
    
    async def get_recent_kills(self, guild_id: int, server_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent kill events for server"""
        cursor = self.kill_events.find(
            {"guild_id": guild_id, "server_id": server_id}
        ).sort("timestamp", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    # ECONOMY (Guild-scoped)
    async def get_wallet(self, guild_id: int, discord_id: int) -> Dict[str, Any]:
        """Get user wallet (guild-scoped)"""
        wallet = await self.economy.find_one({"guild_id": guild_id, "discord_id": discord_id})
        
        if not wallet:
            wallet = {
                "guild_id": guild_id,
                "discord_id": discord_id,
                "balance": 0,
                "total_earned": 0,
                "total_spent": 0,
                "created_at": datetime.now(timezone.utc)
            }
            await self.economy.insert_one(wallet)
        
        return wallet
    
    async def update_wallet(self, guild_id: int, discord_id: int, amount: int, 
                           transaction_type: str) -> bool:
        """Update user wallet balance"""
        try:
            update_query = {"$inc": {"balance": amount}}
            
            if amount > 0:
                update_query["$inc"]["total_earned"] = amount
            else:
                update_query["$inc"]["total_spent"] = abs(amount)
            
            update_query["$set"] = {"last_updated": datetime.now(timezone.utc)}
            
            result = await self.economy.update_one(
                {"guild_id": guild_id, "discord_id": discord_id},
                update_query,
                upsert=True
            )
            
            return result.acknowledged
            
        except Exception as e:
            logger.error(f"Failed to update wallet: {e}")
            return False
    
    # PREMIUM (Server-scoped)
    async def set_premium_status(self, guild_id: int, server_id: str, 
                                expires_at: Optional[datetime] = None) -> bool:
        """Set premium status for specific server"""
        try:
            premium_doc = {
                "guild_id": guild_id,
                "server_id": server_id,
                "active": expires_at is not None,
                "expires_at": expires_at,
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.premium.update_one(
                {"guild_id": guild_id, "server_id": server_id},
                {"$set": premium_doc},
                upsert=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set premium status: {e}")
            return False
    
    async def is_premium_server(self, guild_id: int, server_id: str) -> bool:
        """Check if server has active premium"""
        premium_doc = await self.premium.find_one({"guild_id": guild_id, "server_id": server_id})
        
        if not premium_doc or not premium_doc.get("active"):
            return False
        
        if premium_doc.get("expires_at") and premium_doc["expires_at"] < datetime.now(timezone.utc):
            # Premium expired, update status
            await self.set_premium_status(guild_id, server_id, None)
            return False
        
        return True
    
    # LEADERBOARDS
    async def get_leaderboard(self, guild_id: int, server_id: str, stat: str = "kills", 
                             limit: int = 10) -> List[Dict[str, Any]]:
        """Get leaderboard for specific stat"""
        sort_order = -1 if stat in ["kills", "kdr", "longest_streak"] else 1
        
        cursor = self.pvp_data.find(
            {"guild_id": guild_id, "server_id": server_id}
        ).sort(stat, sort_order).limit(limit)
        
        return await cursor.to_list(length=limit)