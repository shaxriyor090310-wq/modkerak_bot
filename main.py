import telebot
from telebot import types
import sqlite3
import time
from flask import Flask, request

TOKEN = "8638161881:AAHRFk9sVr7c8f7xtnUyJF38sg0ODrbWW94"
OWNER_ID = 1331356868

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ---------------- DATABASE ----------------
db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
username TEXT,
name TEXT,
join_time INTEGER
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS admins(
id INTEGER PRIMARY KEY
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS channels(
id INTEGER PRIMARY KEY AUTOINCREMENT,
channel TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS mods(
mod_id INTEGER PRIMARY KEY AUTOINCREMENT,
photo TEXT,
caption TEXT,
file_id TEXT
)""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_users ON users(id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_mods ON mods(mod_id)")
db.commit()

# OWNER ni admin qilish
cur.execute("INSERT OR IGNORE INTO admins(id) VALUES(?)", (OWNER_ID,))
db.commit()

# ---------------- FUNKSIYALAR ----------------
def is_admin(user_id):
    cur.execute("SELECT id FROM admins WHERE id=?", (user_id,))
    return cur.fetchone() is not None

def save_user(message):
    uid = message.from_user.id
    username = message.from_user.username
    name = message.from_user.first_name

    cur.execute("INSERT OR IGNORE INTO users VALUES(?,?,?,?)",
                (uid, username, name, int(time.time())))
    db.commit()

def check_sub(user_id):
    cur.execute("SELECT channel FROM channels")
    channels = cur.fetchall()

    for ch in channels:
        try:
            status = bot.get_chat_member(ch[0], user_id).status
            if status == "left":
                return False
        except:
            return False
    return True

def join_menu():
    markup = types.InlineKeyboardMarkup()
    cur.execute("SELECT channel FROM channels")
    channels = cur.fetchall()

    for ch in channels:
        markup.add(types.InlineKeyboardButton("📢 Kanal", url=f"https://t.me/{ch[0].replace('@','')}"))

    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="checksub"))
    return markup

# ---------------- START ----------------
@bot.message_handler(commands=['start'])
def start(message):

    save_user(message)

    if not check_sub(message.from_user.id):
        bot.send_message(message.chat.id,
        "❗ Botdan foydalanish uchun kanallarga obuna bo‘ling",
        reply_markup=join_menu())
        return

    bot.send_message(message.chat.id,
    "🤖 Bot ishlayapti\n\nMod raqamini yuboring.")

# ---------------- SUB CHECK ----------------
@bot.callback_query_handler(func=lambda c: c.data == "checksub")
def check(call):

    if check_sub(call.from_user.id):
        bot.send_message(call.message.chat.id, "✅ Obuna tasdiqlandi")
    else:
        bot.answer_callback_query(call.id, "❌ Hali obuna bo‘lmadingiz")

# ---------------- MOD KO‘RISH ----------------
@bot.message_handler(func=lambda m: m.text.isdigit())
def mod_view(message):

    mod_id = int(message.text)

    cur.execute("SELECT photo, caption, file_id FROM mods WHERE mod_id=?", (mod_id,))
    mod = cur.fetchone()

    if mod:

        if mod[0]:
            bot.send_photo(message.chat.id, mod[0], caption=f"{mod[1]}\n\n📥 Yuklash ↓")
        else:
            bot.send_message(message.chat.id, mod[1])

        bot.send_document(message.chat.id, mod[2])

    else:
        bot.send_message(message.chat.id, "❌ Mod topilmadi")

# ---------------- MOD QO‘SHISH ----------------
@bot.message_handler(commands=['addmod'])
def add_mod(message):

    if not is_admin(message.from_user.id):
        return

    msg = bot.send_message(message.chat.id, "📸 Mod rasmi yuboring")
    bot.register_next_step_handler(msg, mod_photo)

def mod_photo(message):

    photo = message.photo[-1].file_id

    msg = bot.send_message(message.chat.id, "📝 Tavsif yuboring")
    bot.register_next_step_handler(msg, mod_caption, photo)

def mod_caption(message, photo):

    caption = message.text

    msg = bot.send_message(message.chat.id, "📦 Fayl yuboring")
    bot.register_next_step_handler(msg, mod_file, photo, caption)

def mod_file(message, photo, caption):

    file_id = message.document.file_id

    cur.execute("INSERT INTO mods(photo,caption,file_id) VALUES(?,?,?)",
                (photo, caption, file_id))
    db.commit()

    bot.send_message(message.chat.id, "✅ Mod qo‘shildi")

# ---------------- MOD DELETE ----------------
@bot.message_handler(commands=['delmod'])
def del_mod(message):

    if not is_admin(message.from_user.id):
        return

    try:
        mod_id = int(message.text.split()[1])
        cur.execute("DELETE FROM mods WHERE mod_id=?", (mod_id,))
        db.commit()

        bot.send_message(message.chat.id, "🗑 Mod o‘chirildi")
    except:
        bot.send_message(message.chat.id, "❌ Format: /delmod 1")

# ---------------- ADD ADMIN ----------------
@bot.message_handler(commands=['addadmin'])
def add_admin(message):

    if message.from_user.id != OWNER_ID:
        return

    admin_id = int(message.text.split()[1])

    cur.execute("INSERT OR IGNORE INTO admins VALUES(?)", (admin_id,))
    db.commit()

    bot.send_message(message.chat.id, "👑 Admin qo‘shildi")

# ---------------- ADMIN LIST ----------------
@bot.message_handler(commands=['admins'])
def admins(message):

    if not is_admin(message.from_user.id):
        return

    cur.execute("SELECT id FROM admins")
    data = cur.fetchall()

    text = "👑 Adminlar:\n"
    for a in data:
        text += f"{a[0]}\n"

    bot.send_message(message.chat.id, text)

# ---------------- STAT ----------------
@bot.message_handler(commands=['stat'])
def stat(message):

    if not is_admin(message.from_user.id):
        return

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM mods")
    mods = cur.fetchone()[0]

    bot.send_message(message.chat.id,
    f"👥 User: {users}\n📦 Modlar: {mods}")

# ---------------- BROADCAST ----------------
@bot.message_handler(commands=['broadcast'])
def broadcast(message):

    if not is_admin(message.from_user.id):
        return

    msg = message.text.replace("/broadcast ", "")

    cur.execute("SELECT id FROM users")
    users = cur.fetchall()

    sent = 0

    for u in users:
        try:
            bot.send_message(u[0], msg)
            sent += 1
        except:
            pass

    bot.send_message(message.chat.id, f"📢 Yuborildi: {sent}")

# ---------------- ADD CHANNEL ----------------
@bot.message_handler(commands=['addchannel'])
def add_channel(message):

    if not is_admin(message.from_user.id):
        return

    channel = message.text.split()[1]

    cur.execute("INSERT INTO channels(channel) VALUES(?)", (channel,))
    db.commit()

    bot.send_message(message.chat.id, "✅ Kanal qo‘shildi")

# ---------------- WEBHOOK ----------------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():

    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)

    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot ishlayapti"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
