"""
Emerald's Killfeed - Advanced Embed System v4.0
Centralized EmbedFactory for all embed types with thematic styling
"""

import discord
import random
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

class EmbedFactory:
    """
    Centralized factory for creating all bot embeds with consistent styling
    and thematic combat log messages appropriate to Deadside environment
    """
    
    # Color constants
    COLORS = {
        'killfeed': 0x00d38a,
        'suicide': 0xff5e5e,
        'fall': 0xc084fc,
        'slots': 0x7f5af0,
        'roulette': 0xef4444,
        'blackjack': 0x22c55e,
        'profile': 0x00d38a,
        'bounty': 0xfacc15,
        'admin': 0x64748b
    }
    
    # Title pools for different embed types
    TITLE_POOLS = {
        'killfeed': [
            "Silhouette Erased",
            "Hostile Removed", 
            "Contact Dismantled",
            "Kill Confirmed",
            "Eyes Off Target"
        ],
        'suicide': [
            "Self-Termination Logged",
            "Manual Override",
            "Exit Chosen"
        ],
        'fall': [
            "Gravity Kill Logged",
            "Terminal Descent",
            "Cliffside Casualty"
        ],
        'bounty': [
            "Target Flagged",
            "HVT Logged", 
            "Kill Contract Active"
        ]
    }
    
    # Combat log message pools
    COMBAT_LOGS = {
        'kill': [
            "Another shadow fades from the wasteland.",
            "The survivor count drops by one.",
            "Territory claimed through violence.",
            "Blood marks another chapter in survival.",
            "The weak have been culled from the herd.",
            "Death arrives on schedule in Deadside.",
            "One less mouth to feed in this barren world.",
            "The food chain adjusts itself once more."
        ],
        'suicide': [
            "Sometimes the only escape is through the void.",
            "The wasteland claims another volunteer.",
            "Exit strategy: permanent.",
            "Final decision executed successfully.",
            "The burden of survival lifted by choice.",
            "Another soul releases itself from this hell."
        ],
        'fall': [
            "Gravity shows no mercy in the wasteland.",
            "The ground always wins in the end.",
            "Physics delivers its final verdict.",
            "Another lesson in terminal velocity.",
            "The earth reclaims what fell from above.",
            "Descent complete. No survivors."
        ],
        'gambling': [
            "Fortune favors the desperate in Deadside.",
            "The house edge cuts deeper than any blade.",
            "Luck is just another scarce resource here.",
            "Survived the dealer. Survived the odds.",
            "In this wasteland, even chance is hostile.",
            "Risk and reward dance their eternal waltz."
        ],
        'bounty': [
            "A price on their head. A target on their back.",
            "The hunter becomes the hunted.",
            "Blood money flows through these lands.",
            "Marked for termination by popular demand.",
            "Contract issued. Payment pending delivery.",
            "The kill order has been authorized."
        ]
    }
    
    @classmethod
    async def build(cls, embed_type: str, data: Dict[str, Any]) -> discord.Embed:
        """
        Build an embed of the specified type with provided data
        
        Args:
            embed_type: Type of embed to create
            data: Data dictionary containing embed content
            
        Returns:
            Configured Discord embed
        """
        if embed_type == 'killfeed':
            return cls._build_killfeed(data)
        elif embed_type == 'suicide':
            return cls._build_suicide(data)
        elif embed_type == 'fall':
            return cls._build_fall(data)
        elif embed_type == 'slots':
            return cls._build_slots(data)
        elif embed_type == 'roulette':
            return cls._build_roulette(data)
        elif embed_type == 'blackjack':
            return cls._build_blackjack(data)
        elif embed_type == 'profile':
            return cls._build_profile(data)
        elif embed_type == 'bounty':
            return cls._build_bounty(data)
        elif embed_type == 'admin':
            return cls._build_admin(data)
        else:
            raise ValueError(f"Unknown embed type: {embed_type}")
    
    @classmethod
    def _build_killfeed(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build modern killfeed embed - clean aesthetic with themed title and right-aligned logo"""
        # Restore themed titles from the title pool
        title = random.choice(cls.TITLE_POOLS['killfeed']).upper()
        
        # Create clean embed with themed title
        embed = discord.Embed(
            title=title,
            color=cls.COLORS['killfeed'],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Main kill description - clean, bold format
        killer_name = data.get('killer_name', 'Unknown')
        victim_name = data.get('victim_name', 'Unknown')
        killer_kdr = data.get('killer_kdr', '0.00')
        victim_kdr = data.get('victim_kdr', '0.00')
        
        # Primary kill info in description (like the screenshot)
        kill_text = f"**{killer_name}** (KDR: {killer_kdr})\neliminated\n**{victim_name}** (KDR: {victim_kdr})"
        embed.description = kill_text
        
        # Weapon and distance info - clean format
        weapon = data.get('weapon', 'Unknown')
        distance = data.get('distance', '0')
        
        weapon_text = f"**Weapon:** {weapon}\n**From** {distance} Meters"
        embed.add_field(name="", value=weapon_text, inline=False)
        
        # Combat log message - atmospheric flavor text
        combat_msg = random.choice(cls.COMBAT_LOGS['kill'])
        embed.add_field(name="", value=f"*{combat_msg}*", inline=False)
        
        # Right-aligned logo as small thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://Killfeed.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Server info footer (like in the screenshot)
        timestamp_str = datetime.now().strftime("%m/%d/%Y %I:%M %p")
        embed.set_footer(text=f"Server: Emerald EU | discord.gg/EmeraldServers | {timestamp_str}")
        
        return embed
    
    @classmethod
    def _build_suicide(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build suicide embed"""
        title = random.choice(cls.TITLE_POOLS['suicide'])
        embed = discord.Embed(
            title=title,
            color=cls.COLORS['suicide'],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Subject
        faction = f" [{data.get('faction')}]" if data.get('faction') else ""
        embed.add_field(
            name="Subject",
            value=f"{data.get('player_name', 'Unknown')}{faction}",
            inline=True
        )
        
        # Cause
        cause = data.get('cause', 'Menu Suicide')
        embed.add_field(
            name="Cause",
            value=cause,
            inline=True
        )
        
        # Combat log
        combat_log = random.choice(cls.COMBAT_LOGS['suicide'])
        embed.add_field(
            name="Combat Log",
            value=combat_log,
            inline=False
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://main.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    def _build_fall(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build fall damage embed"""
        title = random.choice(cls.TITLE_POOLS['fall'])
        embed = discord.Embed(
            title=title,
            color=cls.COLORS['fall'],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Subject
        faction = f" [{data.get('faction')}]" if data.get('faction') else ""
        embed.add_field(
            name="Subject",
            value=f"{data.get('player_name', 'Unknown')}{faction}",
            inline=True
        )
        
        # Combat log
        combat_log = random.choice(cls.COMBAT_LOGS['fall'])
        embed.add_field(
            name="Combat Log",
            value=combat_log,
            inline=False
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://main.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    def _build_slots(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build slots gambling embed"""
        embed = discord.Embed(
            title="🎰 Wasteland Slots",
            color=cls.COLORS['slots'],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Initial spinning state
        if data.get('state') == 'spinning':
            embed.add_field(
                name="Reels",
                value="🎰 | ⏳ | ⏳ | ⏳",
                inline=False
            )
            embed.add_field(
                name="Status",
                value="Spinning...",
                inline=False
            )
        else:
            # Final result
            if data.get('win'):
                embed.add_field(
                    name="Reels",
                    value="🎰 | 💀 | 💀 | 💀",
                    inline=False
                )
                embed.add_field(
                    name="Result",
                    value="JACKPOT",
                    inline=True
                )
                embed.add_field(
                    name="Payout",
                    value=f"+{data.get('payout', 1200)} EMD",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Reels",
                    value="🎰 | 🧻 | 🥫 | 🧦",
                    inline=False
                )
                embed.add_field(
                    name="Result",
                    value="LOSS",
                    inline=True
                )
                embed.add_field(
                    name="Outcome",
                    value="Deadside's house always wins.",
                    inline=False
                )
        
        # Combat log
        combat_log = random.choice(cls.COMBAT_LOGS['gambling'])
        embed.add_field(
            name="Combat Log",
            value=combat_log,
            inline=False
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://main.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    def _build_roulette(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build roulette gambling embed"""
        embed = discord.Embed(
            title="🎯 Deadside Roulette",
            color=cls.COLORS['roulette'],
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Player Pick",
            value=data.get('player_pick', 'Red'),
            inline=True
        )
        
        embed.add_field(
            name="Spin Result",
            value=data.get('result', 'Black 13'),
            inline=True
        )
        
        embed.add_field(
            name="Outcome",
            value="WIN" if data.get('win') else "LOSS",
            inline=True
        )
        
        if data.get('win'):
            embed.add_field(
                name="Payout",
                value=f"+{data.get('payout', 0)} EMD",
                inline=True
            )
        else:
            embed.add_field(
                name="Loss",
                value=f"-{data.get('bet_amount', 0)} EMD",
                inline=True
            )
        
        # Combat log with dark tone
        logs = [
            "The wheel of fortune spins in death's favor.",
            "Luck is a finite resource in this wasteland.",
            "Another gambler learns the house advantage."
        ]
        embed.add_field(
            name="Combat Log",
            value=random.choice(logs),
            inline=False
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://main.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    def _build_blackjack(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build blackjack gambling embed"""
        embed = discord.Embed(
            title="🃏 Wasteland Blackjack",
            color=cls.COLORS['blackjack'],
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Player Hand",
            value=f"{data.get('player_hand', '??')} (Total: {data.get('player_total', 0)})",
            inline=False
        )
        
        embed.add_field(
            name="Dealer Hand", 
            value=f"{data.get('dealer_hand', '??')} (Total: {data.get('dealer_total', 0)})",
            inline=False
        )
        
        embed.add_field(
            name="Outcome",
            value=data.get('outcome', 'Push'),
            inline=True
        )
        
        if data.get('payout', 0) > 0:
            embed.add_field(
                name="Payout",
                value=f"+{data.get('payout')} EMD",
                inline=True
            )
        elif data.get('loss', 0) > 0:
            embed.add_field(
                name="Loss",
                value=f"-{data.get('loss')} EMD", 
                inline=True
            )
        
        # Combat log
        embed.add_field(
            name="Combat Log",
            value="Survived the dealer. Survived the odds.",
            inline=False
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://main.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    def _build_profile(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build player profile embed"""
        embed = discord.Embed(
            title="Combat Record",
            color=cls.COLORS['profile'],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Name with faction
        faction = f" [{data.get('faction')}]" if data.get('faction') else ""
        embed.add_field(
            name="Name",
            value=f"{data.get('player_name', 'Unknown')}{faction}",
            inline=True
        )
        
        embed.add_field(
            name="Kills",
            value=f"{data.get('kills', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="Deaths",
            value=f"{data.get('deaths', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="KDR",
            value=f"{data.get('kdr', '0.00')}",
            inline=True
        )
        
        embed.add_field(
            name="Longest Streak",
            value=f"{data.get('longest_streak', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="Top Weapon",
            value=data.get('top_weapon', 'None'),
            inline=True
        )
        
        embed.add_field(
            name="Rival",
            value=data.get('rival', 'None'),
            inline=True
        )
        
        embed.add_field(
            name="Nemesis", 
            value=data.get('nemesis', 'None'),
            inline=True
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://main.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    def _build_bounty(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build bounty embed"""
        title = random.choice(cls.TITLE_POOLS['bounty'])
        embed = discord.Embed(
            title=title,
            color=cls.COLORS['bounty'],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Target with faction
        faction = f" [{data.get('target_faction')}]" if data.get('target_faction') else ""
        embed.add_field(
            name="Target",
            value=f"{data.get('target_name', 'Unknown')}{faction}",
            inline=True
        )
        
        embed.add_field(
            name="Bounty Amount",
            value=f"{data.get('amount', 0)} EMD",
            inline=True
        )
        
        embed.add_field(
            name="Set by",
            value=data.get('set_by', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="Reason",
            value=data.get('reason', 'High-value target'),
            inline=True
        )
        
        embed.add_field(
            name="Time Remaining",
            value=data.get('time_remaining', '24h'),
            inline=True
        )
        
        # Combat log
        combat_log = random.choice(cls.COMBAT_LOGS['bounty'])
        embed.add_field(
            name="Combat Log",
            value=combat_log,
            inline=False
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://Bounty.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    def _build_admin(cls, data: Dict[str, Any]) -> discord.Embed:
        """Build admin command embed"""
        embed = discord.Embed(
            title="System Command Executed",
            color=cls.COLORS['admin'],
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Executor",
            value=data.get('executor', 'System'),
            inline=True
        )
        
        embed.add_field(
            name="Target",
            value=data.get('target', 'N/A'),
            inline=True
        )
        
        embed.add_field(
            name="Command",
            value=data.get('command', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="Timestamp",
            value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:R>",
            inline=True
        )
        
        embed.add_field(
            name="Outcome",
            value=data.get('outcome', 'Success'),
            inline=True
        )
        
        # Thumbnail
        thumbnail_url = data.get('thumbnail_url', 'attachment://main.png')
        embed.set_thumbnail(url=thumbnail_url)
        
        # Footer
        embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
        
        return embed
    
    @classmethod
    async def build_animated_slots(cls, ctx, data: Dict[str, Any]) -> discord.Message:
        """
        Build animated slots embed with edit-based illusion
        
        Args:
            ctx: Discord application context
            data: Slots data including win/loss info
            
        Returns:
            Final message after animation
        """
        # Step 1: Send spinning embed
        spinning_data = {**data, 'state': 'spinning'}
        spinning_embed = cls._build_slots(spinning_data)
        message = await ctx.respond(embed=spinning_embed)
        
        # Step 2: Wait 2 seconds then edit to final result
        await asyncio.sleep(2)
        final_data = {**data, 'state': 'final'}
        final_embed = cls._build_slots(final_data)
        await message.edit_original_response(embed=final_embed)
        
        return message