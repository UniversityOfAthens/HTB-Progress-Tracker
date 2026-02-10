import discord
from discord.ext import tasks, commands
import requests
import json
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime, time
from zoneinfo import ZoneInfo

from utils.update_root_flags import check_root_flags_manual

# ================= CONFIGURATION =================
# Load the .env file
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HTB_API_TOKEN = os.getenv("HTB_API_TOKEN")
CHANNEL_ID_STR = os.getenv("CHANNEL_ID")
HTB_API_URL = os.getenv("HTB_API_URL")

# Check if the required keys exist
if not DISCORD_TOKEN or not HTB_API_TOKEN or not CHANNEL_ID_STR:
    print(
        "❌ ERROR: Missing keys in .env file! Ensure DISCORD_TOKEN, HTB_API_TOKEN, and CHANNEL_ID are set."
    )
    exit()

try:
    CHANNEL_ID = int(CHANNEL_ID_STR)
except ValueError:
    print("❌ ERROR: CHANNEL_ID in .env must be a number.")
    exit()

# --- WEEKLY GOALS ---
GOAL_MACHINES = 1
GOAL_CHALLENGES = 2

DB_FILE = "htb_data.json"
# =================================================

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ================= DATABASE FUNCTIONS =================
def load_db():
    data = {"users": {}}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ JSON Corrupt. Starting fresh (Old file backed up).")
            os.rename(DB_FILE, f"{DB_FILE}.bak")

    # Migration for old data
    if "users" in data:
        for uid, user_data in data["users"].items():
            if "streak" not in user_data:
                user_data["streak"] = 0
            if "user_flag_ids" not in user_data:
                user_data["user_flag_ids"] = []
            if "root_flag_ids" not in user_data:
                user_data["root_flag_ids"] = []
    return data


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


db = load_db()


# ================= HTB API HELPER =================
def make_htb_request(endpoint):
    url = f"{HTB_API_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {HTB_API_TOKEN}",
        "User-Agent": "DiscordBot/1.0",
        "Accept": "application/json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        elif response.status_code == 401:
            print(f"⚠️ 401 Unauthorized: Check your HTB_API_TOKEN.")
            return None
        else:
            print(f"⚠️ API Error {response.status_code} on {url}")
            return None
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None


def get_user_activity(user_id):
    """Returns activity (User/Root separated)."""
    data = make_htb_request(f"/api/v4/user/profile/activity/{user_id}")
    if data:
        return data.get("profile", {}).get("activity", [])
    return None


def get_user_details(user_id):
    """Returns Name and Avatar URL."""
    data = make_htb_request(f"/api/v4/user/profile/basic/{user_id}")
    if data:
        profile = data.get("profile", {})
        name = profile.get("name", "Unknown")
        avatar = profile.get("avatar")
        if avatar and avatar.startswith("/"):
            avatar = f"https://labs.hackthebox.com{avatar}"
        if not avatar:
            avatar = "https://labs.hackthebox.com/images/logo-htb.png"
        return name, avatar
    return "Unknown", "https://labs.hackthebox.com/images/logo-htb.png"


def get_challenge_info(challenge_id):
    data = make_htb_request(f"/api/v4/challenge/info/{challenge_id}")
    if data:
        return data.get("challenge", {}).get("category_name")
    return None


# ================= CORE LOGIC (RESET) =================


async def perform_reset_logic(channel):
    """The central Reset logic (for Command and Scheduler)."""
    completed_list = []
    failed_list = []
    loser_mentions = []  # List for mentions (pings)

    for uid, user in db["users"].items():
        m_count = user.get("machines", 0)
        c_count = user.get("challenges", 0)

        goals_met = (m_count >= GOAL_MACHINES) and (c_count >= GOAL_CHALLENGES)

        if goals_met:
            user["streak"] = user.get("streak", 0) + 1
            completed_list.append(f"🔥 **{user['name']}** (Streak: {user['streak']})")
        else:
            user["streak"] = 0
            failed_list.append(
                f"💀 **{user['name']}** ({m_count}/{GOAL_MACHINES} 🖥️, {c_count}/{GOAL_CHALLENGES} 🧩)"
            )

            # Collect Discord ID for roasting
            if "discord_id" in user:
                loser_mentions.append(f"<@{user['discord_id']}>")

        # Reset for the new week
        user["machines"] = 0
        user["challenges"] = 0

    save_db(db)

    # Report Embed
    embed = discord.Embed(
        title="🗓️ Weekly Reset & Report",
        description="The week has ended! Here is the breakdown:",
        color=discord.Color.dark_grey(),
    )

    def format_list(lst):
        text = "\n".join(lst)
        return text[:1000] + "..." if len(text) > 1000 else text

    if completed_list:
        embed.add_field(
            name="✅ Goal Achieved", value=format_list(completed_list), inline=False
        )
    else:
        embed.add_field(
            name="✅ Goal Achieved",
            value="None... 😢 Do better next week!",
            inline=False,
        )

    if failed_list:
        embed.add_field(
            name="❌ Missed Goals", value=format_list(failed_list), inline=False
        )
    else:
        embed.add_field(
            name="❌ Missed Goals", value="None! Everyone is a Legend! 🎉", inline=False
        )

    # 1. Send the Report Embed
    await channel.send(embed=embed)

    # 2. Send the Shame Message with Pings (if there are failures)
    if loser_mentions:
        pings_str = " ".join(loser_mentions)
        await channel.send(f"{pings_str} why you slack bro 📉")


# ================= COMMANDS =================


@bot.command()
async def track(ctx):
    """Starts the tracking process via DM."""
    await ctx.send(f"{ctx.author.mention} Check your DMs!")
    try:
        await ctx.author.send(
            "👋 Reply with your **HackTheBox User ID** (numbers only)."
        )

        def check(m):
            return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)

        msg = await bot.wait_for("message", check=check, timeout=600.0)

        if not msg.content.isdigit():
            await ctx.author.send("❌ Numbers only.")
            return

        htb_id = msg.content
        await ctx.author.send(f"🔍 Verifying ID {htb_id}...")

        htb_name, htb_avatar = get_user_details(htb_id)

        if htb_name == "Unknown":
            await ctx.author.send("❌ ID not found.")
            return

        if htb_id not in db["users"]:
            await ctx.author.send("🔄 Initializing...")
            # Bring the old ones so we don't count them as new
            initial_activity = get_user_activity(htb_id)
            existing_ids = (
                [act["id"] for act in initial_activity] if initial_activity else []
            )

            db["users"][htb_id] = {
                "name": htb_name,
                "discord_id": ctx.author.id,
                "machines": 0,
                "challenges": 0,
                "streak": 0,
                "solved_ids": existing_ids,
                "user_flag_ids": [],  # Track user flags separately
                "root_flag_ids": [],  # Track root flags
            }
            save_db(db)
            await ctx.author.send(f"✅ Success! Tracking **{htb_name}**.")

            main_channel = bot.get_channel(CHANNEL_ID)
            if main_channel:
                embed = discord.Embed(
                    title="🕵️ New Agent Tracked!",
                    description=f"**[{htb_name}](https://app.hackthebox.com/users/{htb_id})** joined.",
                    color=discord.Color.blue(),
                )
                embed.set_thumbnail(url=htb_avatar)
                await main_channel.send(embed=embed)
        else:
            await ctx.author.send(f"⚠️ **{htb_name}** is already tracked!")

    except asyncio.TimeoutError:
        await ctx.author.send("⏰ Timed out.")
    except discord.Forbidden:
        await ctx.send("❌ Enable DMs.")


@bot.command()
async def untrack(ctx):
    """Stops the tracking."""
    id_to_remove = None
    for htb_id, data in db["users"].items():
        if data["discord_id"] == ctx.author.id:
            id_to_remove = htb_id
            break
    if id_to_remove:
        del db["users"][id_to_remove]
        save_db(db)
        await ctx.send(f"🗑️ Stopped tracking.")
    else:
        await ctx.send("❓ Not tracked.")


@bot.command()
async def stats(ctx):
    """Personal weekly stats."""
    found = False
    for htb_id, data in db["users"].items():
        if data["discord_id"] == ctx.author.id:
            found = True
            m_prog = data.get("machines", 0)
            c_prog = data.get("challenges", 0)
            streak = data.get("streak", 0)

            embed = discord.Embed(
                title=f"📊 Stats for {data['name']}", color=discord.Color.purple()
            )
            embed.add_field(
                name="Progress",
                value=f"🖥️ {m_prog}/{GOAL_MACHINES}\n🧩 {c_prog}/{GOAL_CHALLENGES}",
                inline=True,
            )
            embed.add_field(name="Streak", value=f"{streak} weeks 🔥", inline=True)
            await ctx.send(embed=embed)
            break
    if not found:
        await ctx.send("❌ Use `!track`.")


@bot.command()
async def top(ctx):
    """Shows the leaderboard (Top 10 regardless of score)."""
    if not db["users"]:
        await ctx.send("📉 No users are being tracked yet!")
        return

    leaderboard_data = []

    for user_id, data in db["users"].items():
        m = data.get("machines", 0)
        c = data.get("challenges", 0)
        s = data.get("streak", 0)
        total_score = m + c

        # Add ALL users
        leaderboard_data.append((user_id, data["name"], m, c, s, total_score))

    # Sort: First Score, then Streak (descending)
    leaderboard_data.sort(key=lambda x: (x[5], x[4]), reverse=True)

    embed = discord.Embed(
        title="🏆 Weekly Hacker Leaderboard", color=discord.Color.gold()
    )
    embed.description = "Ranked by Total Solves (Machines + Challenges)"

    medals = ["🥇", "🥈", "🥉"]

    # Show Top 10
    for rank, user in enumerate(leaderboard_data[:10]):
        uid, name, mach, chall, streak, score = user

        if rank < 3:
            rank_icon = medals[rank]
        else:
            rank_icon = f"**#{rank + 1}**"

        value_text = f"🖥️ **{mach}**  🧩 **{chall}**  |  🔥 **{streak}**"

        embed.add_field(name=f"{rank_icon} {name}", value=value_text, inline=False)

    embed.set_footer(text=f"Total Tracked Hackers: {len(db['users'])}")
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def reset_week(ctx):
    """Manual Admin Command: Resets stats immediately."""
    await perform_reset_logic(ctx.channel)


# ================= AUTOMATION LOOPS =================


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    if not check_htb_activity.is_running():
        check_htb_activity.start()

    if not scheduled_weekly_reset.is_running():
        scheduled_weekly_reset.start()


@tasks.loop(minutes=10)
async def check_htb_activity():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔎 Check started...")

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"⚠️ Error: Channel ID {CHANNEL_ID} not found.")
        return

    for htb_id, user_data in list(db["users"].items()):

        print(f"   > Scanning activity for User: {user_data['name']} (ID: {htb_id})...")

        activities = get_user_activity(htb_id)
        if activities is None:
            continue

        for activity in reversed(activities):
            act_id = activity.get("id")
            act_type = activity.get("object_type")
            act_name = activity.get("name")
            act_flag_type = activity.get("type")

            # Check if this activity has already been processed
            # For user flags, check user_flag_ids; for others, check solved_ids
            already_processed = False
            if act_type == "machine" and act_flag_type == "user":
                user_flag_id = f"{act_id}_user"
                already_processed = user_flag_id in user_data.get("user_flag_ids", [])
            else:
                already_processed = act_id in user_data["solved_ids"]

            if not already_processed:

                print(f"     ✅ New Solve: {act_name} ({act_type} - {act_flag_type})")

                display_type = ""
                display_suffix = ""
                description_text = ""
                color = discord.Color.green()

                # --- LOGIC CHANGE HERE ---
                should_count = False  # Track if this activity should be counted

                if act_type == "machine":
                    if act_flag_type == "user":
                        # User Flag: Notification ONLY. No point added.
                        display_type = "👤 User Flag"
                        description_text = f"**{act_name}** user access obtained! Keep going for Root! 🚀"
                        color = discord.Color.orange()  # Orange for "Work in Progress"
                        # Don't add to solved_ids - we want to catch the root flag later

                    elif act_flag_type == "root":
                        # Root Flag: Counts as the Machine Solve.
                        user_data["machines"] += 1
                        should_count = True  # This counts, so add to solved_ids
                        display_type = "💀 Root Flag"
                        description_text = (
                            f"**{act_name}** has been fully compromised! System Own3d."
                        )
                        color = discord.Color.red()  # Red for Root/Danger

                        # Update root_flag_ids in database
                        if "root_flag_ids" not in user_data:
                            user_data["root_flag_ids"] = []
                        if act_id not in user_data["root_flag_ids"]:
                            user_data["root_flag_ids"].append(act_id)
                            user_data["root_flag_ids"].sort()  # Keep sorted

                    else:
                        # Fallback just in case
                        display_type = "Machine"
                        description_text = f"**{act_name}** activity detected."
                        should_count = (
                            True  # Unknown type, count it to avoid duplicates
                        )

                elif act_type == "challenge":
                    user_data["challenges"] += 1
                    should_count = True  # Challenges count, so add to solved_ids
                    display_type = "🧩 Challenge"
                    cat_name = get_challenge_info(act_id)
                    if cat_name:
                        display_suffix = f" ({cat_name})"
                    description_text = (
                        f"**{act_name}**{display_suffix} has been solved."
                    )
                    color = discord.Color.green()

                else:
                    display_type = act_type.capitalize()
                    description_text = f"**{act_name}** completed."
                    should_count = True  # Unknown type, count it to avoid duplicates

                # Save ID so we don't alert again - only for activities that count
                if should_count:
                    user_data["solved_ids"].append(act_id)
                else:
                    # For user flags, use a composite key to track them separately
                    # This prevents duplicate notifications while allowing root flags to be processed
                    user_flag_id = f"{act_id}_user"
                    if user_flag_id not in user_data.get("user_flag_ids", []):
                        if "user_flag_ids" not in user_data:
                            user_data["user_flag_ids"] = []
                        user_data["user_flag_ids"].append(user_flag_id)
                _, htb_avatar = get_user_details(htb_id)

                # Build the Embed
                embed = discord.Embed(
                    title=f"🚩 {user_data['name']} got a {display_type}!",
                    description=description_text,
                    color=color,
                )
                embed.set_thumbnail(url=htb_avatar)

                m_prog = user_data["machines"]
                c_prog = user_data["challenges"]
                streak = user_data.get("streak", 0)

                m_status = "✅" if m_prog >= GOAL_MACHINES else "❌"
                c_status = "✅" if c_prog >= GOAL_CHALLENGES else "❌"

                embed.add_field(
                    name="Weekly Progress",
                    value=f"🖥️ {m_prog}/{GOAL_MACHINES} {m_status}\n🧩 {c_prog}/{GOAL_CHALLENGES} {c_status}",
                    inline=True,
                )
                embed.add_field(name="Streak", value=f"{streak} 🔥", inline=True)

                await channel.send(embed=embed)
                save_db(db)


# --- WEEKLY RESET SCHEDULER (SATURDAY 21:00 GREEK TIME) ---
greece_tz = ZoneInfo("Europe/Athens")


@tasks.loop(time=time(hour=21, minute=0, tzinfo=greece_tz))
async def scheduled_weekly_reset():
    """Runs Saturdays at 21:00 Greece time."""

    # Get Greece time
    now_greece = datetime.now(greece_tz)

    # 0=Monday, 5=Saturday
    if now_greece.weekday() == 5:
        print("It is Saturday night (Greece)! Performing Weekly Reset...")
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await perform_reset_logic(channel)
        else:
            print("❌ Cannot perform reset: Channel not found.")


# ================= MANUAL ROOT FLAGS CHECK =================
def check_root_flags_manual_imported():
    """Wrapper to call the imported check_root_flags_manual function."""
    check_root_flags_manual(HTB_API_URL, HTB_API_TOKEN, db)

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("❌ Cannot start: DISCORD_TOKEN is empty.")
