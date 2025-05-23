"""
Emerald's Killfeed - Gambling System (PHASE 4)
/gamble slots, /blackjack, /roulette, /lottery
Must use non-blocking async-safe logic
User-locks to prevent concurrent bets
"""

import asyncio
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

class Gambling(commands.Cog):
    """
    GAMBLING (PREMIUM)
    - /gamble slots, /blackjack, /roulette, /lottery
    - Must use non-blocking async-safe logic
    - User-locks to prevent concurrent bets
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.user_locks: Dict[str, asyncio.Lock] = {}
        self.active_games: Dict[str, str] = {}  # Track active games per user
        self.lottery_pools: Dict[int, Dict[str, Any]] = {}  # Guild lottery pools
        
    def get_user_lock(self, user_key: str) -> asyncio.Lock:
        """Get or create a lock for a user to prevent concurrent bets"""
        if user_key not in self.user_locks:
            self.user_locks[user_key] = asyncio.Lock()
        return self.user_locks[user_key]
    
    async def check_premium_server(self, guild_id: int) -> bool:
        """Check if guild has premium access for gambling features"""
        guild_doc = await self.bot.db_manager.get_guild(guild_id)
        if not guild_doc:
            return False
        
        servers = guild_doc.get('servers', [])
        for server_config in servers:
            server_id = server_config.get('server_id', 'default')
            if await self.bot.db_manager.is_premium_server(guild_id, server_id):
                return True
        
        return False
    
    async def add_wallet_event(self, guild_id: int, discord_id: int, 
                              amount: int, event_type: str, description: str):
        """Add wallet transaction event for tracking"""
        try:
            event_doc = {
                "guild_id": guild_id,
                "discord_id": discord_id,
                "amount": amount,
                "event_type": event_type,
                "description": description,
                "timestamp": datetime.now(timezone.utc)
            }
            
            await self.bot.db_manager.db.wallet_events.insert_one(event_doc)
            
        except Exception as e:
            logger.error(f"Failed to add wallet event: {e}")
    
    @commands.slash_command(name="slots", description="Play slot machine")
    async def slots(self, ctx: discord.ApplicationContext, bet: int):
        """Slot machine gambling game"""
        try:
            guild_id = ctx.guild.id
            discord_id = ctx.user.id
            user_key = f"{guild_id}_{discord_id}"
            
            # Check premium access
            if not await self.check_premium_server(guild_id):
                embed = discord.Embed(
                    title="🔒 Premium Feature",
                    description="Gambling features require premium subscription!",
                    color=0xFF6B6B
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Validate bet amount
            if bet <= 0:
                await ctx.respond("❌ Bet amount must be positive!", ephemeral=True)
                return
            
            if bet > 10000:
                await ctx.respond("❌ Maximum bet is $10,000!", ephemeral=True)
                return
            
            # Use lock to prevent concurrent gambling
            async with self.get_user_lock(user_key):
                # Check if user has enough money
                wallet = await self.bot.db_manager.get_wallet(guild_id, discord_id)
                if wallet['balance'] < bet:
                    await ctx.respond(
                        f"❌ Insufficient funds! You have **${wallet['balance']:,}** but need **${bet:,}**",
                        ephemeral=True
                    )
                    return
                
                # Respond immediately to prevent timeout
                await ctx.defer()
                
                # Slot symbols and their values
                symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '⭐', '7️⃣']
                weights = [30, 25, 20, 15, 5, 3, 2]  # Rarer symbols have lower weights
                
                # Spin the slots
                reels = []
                for _ in range(3):
                    reel = random.choices(symbols, weights=weights)[0]
                    reels.append(reel)
                
                # Calculate winnings
                winnings = 0
                result_text = ""
                
                if reels[0] == reels[1] == reels[2]:  # All three match
                    if reels[0] == '7️⃣':
                        winnings = bet * 100  # Jackpot!
                        result_text = "🎰 **JACKPOT!** 🎰"
                    elif reels[0] == '💎':
                        winnings = bet * 50
                        result_text = "💎 **DIAMOND TRIPLE!** 💎"
                    elif reels[0] == '⭐':
                        winnings = bet * 25
                        result_text = "⭐ **STAR TRIPLE!** ⭐"
                    else:
                        winnings = bet * 10
                        result_text = f"{reels[0]} **TRIPLE!** {reels[0]}"
                        
                elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:  # Two match
                    winnings = bet * 2
                    result_text = "✨ **PAIR!** ✨"
                else:
                    result_text = "💸 **No match** 💸"
                
                # Calculate net result
                net_result = winnings - bet
                
                # Update wallet
                success = await self.bot.db_manager.update_wallet(
                    guild_id, discord_id, net_result, "gambling_slots"
                )
                
                if success:
                    # Add wallet event
                    await self.add_wallet_event(
                        guild_id, discord_id, net_result, "gambling_slots",
                        f"Slots: {' '.join(reels)} | Bet: ${bet:,}"
                    )
                    
                    # Create result embed
                    color = 0x00FF00 if net_result > 0 else 0xFF0000 if net_result < 0 else 0xFFD700
                    
                    embed = discord.Embed(
                        title="🎰 Slot Machine",
                        description=f"**[ {' | '.join(reels)} ]**\n\n{result_text}",
                        color=color,
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    embed.add_field(
                        name="💰 Bet",
                        value=f"${bet:,}",
                        inline=True
                    )
                    
                    if winnings > 0:
                        embed.add_field(
                            name="🎉 Winnings",
                            value=f"${winnings:,}",
                            inline=True
                        )
                    
                    embed.add_field(
                        name="📊 Net Result",
                        value=f"{'**+' if net_result > 0 else ''}${net_result:,}{'**' if net_result > 0 else ''}",
                        inline=True
                    )
                    
                    # Get updated balance
                    updated_wallet = await self.bot.db_manager.get_wallet(guild_id, discord_id)
                    embed.add_field(
                        name="💳 New Balance",
                        value=f"${updated_wallet['balance']:,}",
                        inline=False
                    )
                    
                    embed.set_thumbnail(url="attachment://main.png")
                    embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                    
                    await ctx.followup.send(embed=embed)
                else:
                    await ctx.followup.send("❌ Failed to process bet. Please try again.")
            
        except Exception as e:
            logger.error(f"Failed to process slots: {e}")
            await ctx.respond("❌ Slots game failed. Please try again.", ephemeral=True)
    
    @commands.slash_command(name="blackjack", description="Play blackjack")
    async def blackjack(self, ctx: discord.ApplicationContext, bet: int):
        """Blackjack card game"""
        try:
            guild_id = ctx.guild.id
            discord_id = ctx.user.id
            user_key = f"{guild_id}_{discord_id}"
            
            # Check premium access
            if not await self.check_premium_server(guild_id):
                embed = discord.Embed(
                    title="🔒 Premium Feature",
                    description="Gambling features require premium subscription!",
                    color=0xFF6B6B
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Validate bet
            if bet <= 0:
                await ctx.respond("❌ Bet amount must be positive!", ephemeral=True)
                return
            
            if bet > 5000:
                await ctx.respond("❌ Maximum bet is $5,000!", ephemeral=True)
                return
            
            # Use lock to prevent concurrent games
            async with self.get_user_lock(user_key):
                # Check balance
                wallet = await self.bot.db_manager.get_wallet(guild_id, discord_id)
                if wallet['balance'] < bet:
                    await ctx.respond(
                        f"❌ Insufficient funds! You have **${wallet['balance']:,}** but need **${bet:,}**",
                        ephemeral=True
                    )
                    return
                
                await ctx.defer()
                
                # Create deck
                suits = ['♠️', '♥️', '♦️', '♣️']
                ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
                deck = [f"{rank}{suit}" for suit in suits for rank in ranks]
                random.shuffle(deck)
                
                # Deal initial cards
                player_cards = [deck.pop(), deck.pop()]
                dealer_cards = [deck.pop(), deck.pop()]
                
                def card_value(cards):
                    """Calculate hand value"""
                    value = 0
                    aces = 0
                    
                    for card in cards:
                        rank = card[:-2]  # Remove suit
                        if rank in ['J', 'Q', 'K']:
                            value += 10
                        elif rank == 'A':
                            aces += 1
                            value += 11
                        else:
                            value += int(rank)
                    
                    # Handle aces
                    while value > 21 and aces > 0:
                        value -= 10
                        aces -= 1
                    
                    return value
                
                player_value = card_value(player_cards)
                dealer_value = card_value(dealer_cards)
                
                # Check for natural blackjack
                if player_value == 21 and len(player_cards) == 2:
                    if dealer_value == 21 and len(dealer_cards) == 2:
                        # Push
                        result_text = "🤝 **PUSH** - Both have Blackjack!"
                        winnings = bet  # Return bet
                        net_result = 0
                    else:
                        # Player blackjack
                        result_text = "🎯 **BLACKJACK!** 🎯"
                        winnings = int(bet * 2.5)  # 3:2 payout
                        net_result = winnings - bet
                else:
                    # Dealer plays (hits on soft 17)
                    while dealer_value < 17 or (dealer_value == 17 and any('A' in card for card in dealer_cards)):
                        dealer_cards.append(deck.pop())
                        dealer_value = card_value(dealer_cards)
                    
                    # Determine winner
                    if player_value > 21:
                        result_text = "💥 **BUST!** You went over 21!"
                        winnings = 0
                        net_result = -bet
                    elif dealer_value > 21:
                        result_text = "🎉 **DEALER BUST!** You win!"
                        winnings = bet * 2
                        net_result = bet
                    elif player_value > dealer_value:
                        result_text = "🏆 **YOU WIN!**"
                        winnings = bet * 2
                        net_result = bet
                    elif dealer_value > player_value:
                        result_text = "😔 **DEALER WINS**"
                        winnings = 0
                        net_result = -bet
                    else:
                        result_text = "🤝 **PUSH** - It's a tie!"
                        winnings = bet
                        net_result = 0
                
                # Update wallet
                success = await self.bot.db_manager.update_wallet(
                    guild_id, discord_id, net_result, "gambling_blackjack"
                )
                
                if success:
                    await self.add_wallet_event(
                        guild_id, discord_id, net_result, "gambling_blackjack",
                        f"Blackjack: P:{player_value} D:{dealer_value} | Bet: ${bet:,}"
                    )
                    
                    # Create result embed
                    color = 0x00FF00 if net_result > 0 else 0xFF0000 if net_result < 0 else 0xFFD700
                    
                    embed = discord.Embed(
                        title="🃏 Blackjack",
                        description=result_text,
                        color=color,
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    embed.add_field(
                        name="🎴 Your Hand",
                        value=f"{' '.join(player_cards)}\n**Value: {player_value}**",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="🎭 Dealer Hand",
                        value=f"{' '.join(dealer_cards)}\n**Value: {dealer_value}**",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="📊 Result",
                        value=f"Bet: ${bet:,}\nNet: {'**+' if net_result > 0 else ''}${net_result:,}{'**' if net_result > 0 else ''}",
                        inline=False
                    )
                    
                    embed.set_thumbnail(url="attachment://main.png")
                    embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                    
                    await ctx.followup.send(embed=embed)
                else:
                    await ctx.followup.send("❌ Failed to process bet. Please try again.")
            
        except Exception as e:
            logger.error(f"Failed to process blackjack: {e}")
            await ctx.respond("❌ Blackjack game failed. Please try again.", ephemeral=True)
    
    @commands.slash_command(name="roulette", description="Play roulette")
    async def roulette(self, ctx: discord.ApplicationContext, bet: int, choice: str):
        """Roulette wheel game"""
        try:
            guild_id = ctx.guild.id
            discord_id = ctx.user.id
            user_key = f"{guild_id}_{discord_id}"
            
            # Check premium access
            if not await self.check_premium_server(guild_id):
                embed = discord.Embed(
                    title="🔒 Premium Feature",
                    description="Gambling features require premium subscription!",
                    color=0xFF6B6B
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Validate bet
            if bet <= 0:
                await ctx.respond("❌ Bet amount must be positive!", ephemeral=True)
                return
            
            if bet > 2000:
                await ctx.respond("❌ Maximum bet is $2,000!", ephemeral=True)
                return
            
            # Validate choice
            valid_choices = {
                'red', 'black', 'odd', 'even', 'low', 'high',
                '0', '00'  # Special cases
            }
            
            # Add number choices
            for i in range(1, 37):
                valid_choices.add(str(i))
            
            if choice.lower() not in valid_choices:
                await ctx.respond(
                    "❌ Invalid choice! Use: red, black, odd, even, low (1-18), high (19-36), or specific numbers (0-36, 00)",
                    ephemeral=True
                )
                return
            
            # Use lock to prevent concurrent games
            async with self.get_user_lock(user_key):
                # Check balance
                wallet = await self.bot.db_manager.get_wallet(guild_id, discord_id)
                if wallet['balance'] < bet:
                    await ctx.respond(
                        f"❌ Insufficient funds! You have **${wallet['balance']:,}** but need **${bet:,}**",
                        ephemeral=True
                    )
                    return
                
                await ctx.defer()
                
                # Roulette wheel setup
                red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
                black_numbers = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
                
                # Spin the wheel
                spin_options = ['0', '00'] + [str(i) for i in range(1, 37)]
                result = random.choice(spin_options)
                
                # Calculate winnings
                winnings = 0
                choice_lower = choice.lower()
                
                if choice_lower == result:
                    # Exact number match
                    if result in ['0', '00']:
                        winnings = bet * 35  # Green pays 35:1
                    else:
                        winnings = bet * 35  # Straight up pays 35:1
                        
                elif result not in ['0', '00']:  # Not green
                    result_num = int(result)
                    
                    if choice_lower == 'red' and result_num in red_numbers:
                        winnings = bet * 2
                    elif choice_lower == 'black' and result_num in black_numbers:
                        winnings = bet * 2
                    elif choice_lower == 'odd' and result_num % 2 == 1:
                        winnings = bet * 2
                    elif choice_lower == 'even' and result_num % 2 == 0:
                        winnings = bet * 2
                    elif choice_lower == 'low' and 1 <= result_num <= 18:
                        winnings = bet * 2
                    elif choice_lower == 'high' and 19 <= result_num <= 36:
                        winnings = bet * 2
                
                net_result = winnings - bet
                
                # Update wallet
                success = await self.bot.db_manager.update_wallet(
                    guild_id, discord_id, net_result, "gambling_roulette"
                )
                
                if success:
                    await self.add_wallet_event(
                        guild_id, discord_id, net_result, "gambling_roulette",
                        f"Roulette: {result} | Choice: {choice} | Bet: ${bet:,}"
                    )
                    
                    # Determine result color
                    if result == '0' or result == '00':
                        result_color = '🟢'
                    elif result != '0' and result != '00' and int(result) in red_numbers:
                        result_color = '🔴'
                    else:
                        result_color = '⚫'
                    
                    # Create result embed
                    embed_color = 0x00FF00 if net_result > 0 else 0xFF0000 if net_result < 0 else 0xFFD700
                    
                    embed = discord.Embed(
                        title="🎯 Roulette",
                        description=f"**{result_color} {result}**\n\n{'🎉 **WINNER!**' if winnings > 0 else '💸 **LOSER**'}",
                        color=embed_color,
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    embed.add_field(
                        name="🎲 Your Bet",
                        value=f"**{choice.upper()}** - ${bet:,}",
                        inline=True
                    )
                    
                    if winnings > 0:
                        embed.add_field(
                            name="💰 Winnings",
                            value=f"${winnings:,}",
                            inline=True
                        )
                    
                    embed.add_field(
                        name="📊 Net Result",
                        value=f"{'**+' if net_result > 0 else ''}${net_result:,}{'**' if net_result > 0 else ''}",
                        inline=True
                    )
                    
                    embed.set_thumbnail(url="attachment://main.png")
                    embed.set_footer(text="Powered by Discord.gg/EmeraldServers")
                    
                    await ctx.followup.send(embed=embed)
                else:
                    await ctx.followup.send("❌ Failed to process bet. Please try again.")
            
        except Exception as e:
            logger.error(f"Failed to process roulette: {e}")
            await ctx.respond("❌ Roulette game failed. Please try again.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Gambling(bot))