"""
Emerald's Killfeed - PvP Stats System (PHASE 6)
/stats shows: Kills, deaths, KDR, Suicides, Longest streak, Most used weapon, Rival/Nemesis
/compare <user> compares two profiles
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

class Stats(commands.Cog):
    """
    PVP STATS (FREE)
    - /stats shows: Kills, deaths, KDR, Suicides, Longest streak, Most used weapon, Rival/Nemesis
    - /compare <user> compares two profiles
    """
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_player_combined_stats(self, guild_id: int, player_characters: List[str]) -> Dict[str, Any]:
        """Get combined stats across all servers for a player's characters"""
        try:
            combined_stats = {
                'kills': 0,
                'deaths': 0,
                'suicides': 0,
                'kdr': 0.0,
                'longest_streak': 0,
                'current_streak': 0,
                'total_distance': 0.0,
                'servers_played': 0,
                'favorite_weapon': None,
                'weapon_stats': {},
                'rival': None,
                'nemesis': None
            }
            
            # Get stats from all servers
            for character in player_characters:
                cursor = self.bot.db_manager.pvp_data.find({
                    'guild_id': guild_id,
                    'player_name': character
                })
                
                async for server_stats in cursor:
                    combined_stats['kills'] += server_stats.get('kills', 0)
                    combined_stats['deaths'] += server_stats.get('deaths', 0)
                    combined_stats['suicides'] += server_stats.get('suicides', 0)
                    combined_stats['total_distance'] += server_stats.get('total_distance', 0.0)
                    combined_stats['servers_played'] += 1
                    
                    # Track longest streak
                    if server_stats.get('longest_streak', 0) > combined_stats['longest_streak']:
                        combined_stats['longest_streak'] = server_stats.get('longest_streak', 0)
            
            # Calculate KDR
            combined_stats['kdr'] = combined_stats['kills'] / max(combined_stats['deaths'], 1)
            
            # Get weapon statistics and rivals/nemesis
            await self._calculate_weapon_stats(guild_id, player_characters, combined_stats)
            await self._calculate_rivals_nemesis(guild_id, player_characters, combined_stats)
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"Failed to get combined stats: {e}")
            return combined_stats
    
    async def _calculate_weapon_stats(self, guild_id: int, player_characters: List[str], 
                                    combined_stats: Dict[str, Any]):
        """Calculate weapon statistics from kill events (excludes suicides)"""
        try:
            weapon_counts = {}
            
            for character in player_characters:
                cursor = self.bot.db_manager.kill_events.find({
                    'guild_id': guild_id,
                    'killer': character,
                    'is_suicide': False  # Only count actual PvP kills for weapon stats
                })
                
                async for kill_event in cursor:
                    weapon = kill_event.get('weapon', 'Unknown')
                    # Skip suicide weapons even if they somehow got through
                    if weapon not in ['Menu Suicide', 'Suicide', 'Falling']:
                        weapon_counts[weapon] = weapon_counts.get(weapon, 0) + 1
            
            if weapon_counts:
                combined_stats['favorite_weapon'] = max(weapon_counts, key=weapon_counts.get)
                combined_stats['weapon_stats'] = weapon_counts
            
        except Exception as e:
            logger.error(f"Failed to calculate weapon stats: {e}")
    
    async def _calculate_rivals_nemesis(self, guild_id: int, player_characters: List[str], 
                                      combined_stats: Dict[str, Any]):
        """Calculate rival (most killed) and nemesis (killed by most)"""
        try:
            kills_against = {}
            deaths_to = {}
            
            for character in player_characters:
                # Count kills against others
                cursor = self.bot.db_manager.kill_events.find({
                    'guild_id': guild_id,
                    'killer': character,
                    'is_suicide': False
                })
                
                async for kill_event in cursor:
                    victim = kill_event.get('victim')
                    if victim and victim not in player_characters:  # Don't count alt kills
                        kills_against[victim] = kills_against.get(victim, 0) + 1
                
                # Count deaths to others
                cursor = self.bot.db_manager.kill_events.find({
                    'guild_id': guild_id,
                    'victim': character,
                    'is_suicide': False
                })
                
                async for kill_event in cursor:
                    killer = kill_event.get('killer')
                    if killer and killer not in player_characters:  # Don't count alt deaths
                        deaths_to[killer] = deaths_to.get(killer, 0) + 1
            
            # Set rival and nemesis
            if kills_against:
                combined_stats['rival'] = max(kills_against, key=kills_against.get)
                combined_stats['rival_kills'] = kills_against[combined_stats['rival']]
            
            if deaths_to:
                combined_stats['nemesis'] = max(deaths_to, key=deaths_to.get)
                combined_stats['nemesis_deaths'] = deaths_to[combined_stats['nemesis']]
            
        except Exception as e:
            logger.error(f"Failed to calculate rivals/nemesis: {e}")
    
    @commands.slash_command(name="stats", description="View PvP statistics")
    async def stats(self, ctx: discord.ApplicationContext, user: discord.Member = None):
        """View PvP statistics for yourself or another user"""
        try:
            guild_id = ctx.guild.id
            target_user = user or ctx.user
            
            # Get linked characters
            player_data = await self.bot.db_manager.get_linked_player(guild_id, target_user.id)
            
            if not player_data:
                if target_user == ctx.user:
                    await ctx.respond(
                        "❌ You don't have any linked characters! Use `/link <character>` to get started.",
                        ephemeral=True
                    )
                else:
                    await ctx.respond(
                        f"❌ {target_user.mention} doesn't have any linked characters!",
                        ephemeral=True
                    )
                return
            
            await ctx.defer()
            
            # Get combined stats
            stats = await self.get_player_combined_stats(guild_id, player_data['linked_characters'])
            
            # Create stats embed
            embed = discord.Embed(
                title="📊 PvP Statistics",
                description=f"Combat statistics for {target_user.mention}",
                color=0x3498DB,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Basic stats
            embed.add_field(
                name="⚔️ Combat Stats",
                value=f"**Kills:** {stats['kills']:,}\n"
                      f"**Deaths:** {stats['deaths']:,}\n"
                      f"**Suicides:** {stats['suicides']:,}\n"
                      f"**K/D Ratio:** {stats['kdr']:.2f}",
                inline=True
            )
            
            # Performance stats
            embed.add_field(
                name="🏆 Performance",
                value=f"**Longest Streak:** {stats['longest_streak']:,}\n"
                      f"**Total Distance:** {stats['total_distance']:,.1f}m\n"
                      f"**Servers Played:** {stats['servers_played']:,}",
                inline=True
            )
            
            # Weapon stats
            weapon_text = stats['favorite_weapon'] or 'None'
            if stats['favorite_weapon'] and stats['weapon_stats']:
                weapon_count = stats['weapon_stats'][stats['favorite_weapon']]
                weapon_text = f"{stats['favorite_weapon']} ({weapon_count:,} kills)"
            
            embed.add_field(
                name="🔫 Favorite Weapon",
                value=weapon_text,
                inline=False
            )
            
            # Rival and nemesis
            if stats['rival'] or stats['nemesis']:
                rival_text = f"**Rival:** {stats['rival']} ({stats.get('rival_kills', 0)} kills)" if stats['rival'] else "**Rival:** None"
                nemesis_text = f"**Nemesis:** {stats['nemesis']} ({stats.get('nemesis_deaths', 0)} deaths)" if stats['nemesis'] else "**Nemesis:** None"
                
                embed.add_field(
                    name="🎯 Relationships",
                    value=f"{rival_text}\n{nemesis_text}",
                    inline=False
                )
            
            # Characters
            embed.add_field(
                name="👤 Characters",
                value="\n".join([f"• {char}" for char in player_data['linked_characters']]),
                inline=True
            )
            
            # Set color based on performance
            if stats['kdr'] >= 2.0:
                embed.color = 0x00FF00  # Green for high KDR
            elif stats['kdr'] >= 1.0:
                embed.color = 0xFFD700  # Gold for positive KDR
            else:
                embed.color = 0xFF6B6B  # Red for negative KDR
            
            embed.set_thumbnail(url="attachment://WeaponStats.png")
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to show stats: {e}")
            await ctx.respond("❌ Failed to retrieve statistics.", ephemeral=True)
    
    @commands.slash_command(name="compare", description="Compare stats with another player")
    async def compare(self, ctx: discord.ApplicationContext, user: discord.Member):
        """Compare your stats with another player"""
        try:
            guild_id = ctx.guild.id
            user1 = ctx.user
            user2 = user
            
            if user1.id == user2.id:
                await ctx.respond("❌ You can't compare stats with yourself!", ephemeral=True)
                return
            
            # Get both players' data
            player1_data = await self.bot.db_manager.get_linked_player(guild_id, user1.id)
            player2_data = await self.bot.db_manager.get_linked_player(guild_id, user2.id)
            
            if not player1_data:
                await ctx.respond(
                    "❌ You don't have any linked characters! Use `/link <character>` to get started.",
                    ephemeral=True
                )
                return
            
            if not player2_data:
                await ctx.respond(
                    f"❌ {user2.mention} doesn't have any linked characters!",
                    ephemeral=True
                )
                return
            
            await ctx.defer()
            
            # Get stats for both players
            stats1 = await self.get_player_combined_stats(guild_id, player1_data['linked_characters'])
            stats2 = await self.get_player_combined_stats(guild_id, player2_data['linked_characters'])
            
            # Create comparison embed
            embed = discord.Embed(
                title="⚔️ Player Comparison",
                description=f"{user1.mention} **VS** {user2.mention}",
                color=0x9932CC,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Compare kills
            kills_winner = "🏆" if stats1['kills'] > stats2['kills'] else ("🤝" if stats1['kills'] == stats2['kills'] else "")
            kills_winner2 = "🏆" if stats2['kills'] > stats1['kills'] else ""
            
            embed.add_field(
                name="⚔️ Kills",
                value=f"{kills_winner} **{user1.display_name}:** {stats1['kills']:,}\n"
                      f"{kills_winner2} **{user2.display_name}:** {stats2['kills']:,}",
                inline=True
            )
            
            # Compare deaths
            deaths_winner = "🏆" if stats1['deaths'] < stats2['deaths'] else ("🤝" if stats1['deaths'] == stats2['deaths'] else "")
            deaths_winner2 = "🏆" if stats2['deaths'] < stats1['deaths'] else ""
            
            embed.add_field(
                name="💀 Deaths (Lower is Better)",
                value=f"{deaths_winner} **{user1.display_name}:** {stats1['deaths']:,}\n"
                      f"{deaths_winner2} **{user2.display_name}:** {stats2['deaths']:,}",
                inline=True
            )
            
            # Compare KDR
            kdr_winner = "🏆" if stats1['kdr'] > stats2['kdr'] else ("🤝" if abs(stats1['kdr'] - stats2['kdr']) < 0.01 else "")
            kdr_winner2 = "🏆" if stats2['kdr'] > stats1['kdr'] else ""
            
            embed.add_field(
                name="📊 K/D Ratio",
                value=f"{kdr_winner} **{user1.display_name}:** {stats1['kdr']:.2f}\n"
                      f"{kdr_winner2} **{user2.display_name}:** {stats2['kdr']:.2f}",
                inline=True
            )
            
            # Compare streaks
            streak_winner = "🏆" if stats1['longest_streak'] > stats2['longest_streak'] else ("🤝" if stats1['longest_streak'] == stats2['longest_streak'] else "")
            streak_winner2 = "🏆" if stats2['longest_streak'] > stats1['longest_streak'] else ""
            
            embed.add_field(
                name="🔥 Longest Streak",
                value=f"{streak_winner} **{user1.display_name}:** {stats1['longest_streak']:,}\n"
                      f"{streak_winner2} **{user2.display_name}:** {stats2['longest_streak']:,}",
                inline=True
            )
            
            # Compare distance
            distance_winner = "🏆" if stats1['total_distance'] > stats2['total_distance'] else ("🤝" if abs(stats1['total_distance'] - stats2['total_distance']) < 1 else "")
            distance_winner2 = "🏆" if stats2['total_distance'] > stats1['total_distance'] else ""
            
            embed.add_field(
                name="📏 Total Distance",
                value=f"{distance_winner} **{user1.display_name}:** {stats1['total_distance']:,.1f}m\n"
                      f"{distance_winner2} **{user2.display_name}:** {stats2['total_distance']:,.1f}m",
                inline=True
            )
            
            # Favorite weapons
            weapon1 = stats1['favorite_weapon'] or 'None'
            weapon2 = stats2['favorite_weapon'] or 'None'
            
            embed.add_field(
                name="🔫 Favorite Weapons",
                value=f"**{user1.display_name}:** {weapon1}\n"
                      f"**{user2.display_name}:** {weapon2}",
                inline=False
            )
            
            # Overall winner
            wins1 = sum([
                stats1['kills'] > stats2['kills'],
                stats1['deaths'] < stats2['deaths'],
                stats1['kdr'] > stats2['kdr'],
                stats1['longest_streak'] > stats2['longest_streak'],
                stats1['total_distance'] > stats2['total_distance']
            ])
            
            if wins1 > 2:
                embed.add_field(
                    name="🏆 Overall Winner",
                    value=f"**{user1.mention}** dominates with **{wins1}/5** categories!",
                    inline=False
                )
            elif wins1 < 2:
                embed.add_field(
                    name="🏆 Overall Winner",
                    value=f"**{user2.mention}** dominates with **{5-wins1}/5** categories!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🤝 Result",
                    value="**It's a tie!** Both players are evenly matched.",
                    inline=False
                )
            
            embed.set_thumbnail(url="attachment://WeaponStats.png")
            embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to compare stats: {e}")
            await ctx.respond("❌ Failed to compare statistics.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Stats(bot))