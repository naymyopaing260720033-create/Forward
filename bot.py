import os
import time
import telebot
from datetime import datetime, timedelta

# ==================== BOT TOKEN ====================
# Render မှာ Environment Variable ထည့်ပါ
# ဒါမှမဟုတ် အောက်မှာ Token ကို တိုက်ရိုက်ထည့်ပြီး စမ်းပါ
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Token မပါရင် Error ပြမယ်
if not BOT_TOKEN:
    print("❌ BOT_TOKEN not found in environment variables!")
    print("📌 Please set BOT_TOKEN in Render Environment Variables")
    print("📌 Or hardcode it in the code for testing")
    # စမ်းသပ်ဖို့ ဒီနေရာမှာ Token ထည့်ပြီး အောက်က မှတ်ချက်ဖြုတ်ပါ
    # BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    exit(1)

# Bot ကို Initialize လုပ်မယ်
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    bot.get_me()  # Token မှန်မှန်စစ်မယ်
    print("✅ Bot token is valid!")
except Exception as e:
    print(f"❌ Bot token is invalid: {e}")
    exit(1)

# ==================== STATES ====================
STATE_NONE = 0
STATE_WAITING_FOR_SOURCE = 1
STATE_WAITING_FOR_DESTINATION = 2

# ==================== DATA STORAGE ====================
# User states {user_id: state}
user_states = {}

# User data {user_id: {'source': channel_id, 'destination': channel_id, 'forwarding': bool}}
user_data = {}

# Timeout tracking {user_id: timestamp}
user_timeout = {}

# Processed messages tracking {message_id: True}
processed_messages = {}

# ==================== HELPER FUNCTIONS ====================

def check_admin_status(chat_id):
    """Check if bot is admin in the given channel"""
    try:
        # Get channel info
        chat = bot.get_chat(chat_id)
        
        # Check bot's member status
        bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
        
        if bot_member.status in ['administrator', 'creator']:
            # Get channel info
            title = chat.title
            members_count = getattr(chat, 'members_count', 'Unknown')
            chat_type = 'Public' if chat.username else 'Private'
            username = f"@{chat.username}" if chat.username else "None"
            
            return True, title, members_count, chat_type, username
        else:
            return False, None, None, None, None
            
    except Exception as e:
        # Bot not in channel or channel doesn't exist
        print(f"Admin check error: {e}")
        return False, None, None, None, None

def reset_user_state(user_id):
    """Reset user state and timeout"""
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_timeout:
        del user_timeout[user_id]

def is_channel_id(text):
    """Check if text is a valid channel ID"""
    try:
        channel_id = int(text.strip())
        # Channel IDs usually start with -100
        return str(channel_id).startswith('-100')
    except:
        return False

def get_channel_id_from_text(text):
    """Extract channel ID from text"""
    try:
        return int(text.strip())
    except:
        return None

def format_channel_info(title, members_count, chat_type, username):
    """Format channel info for display"""
    info = f"📌 **Channel:** {title}\n"
    info += f"👥 **Members:** {members_count}\n"
    info += f"🔒 **Type:** {chat_type}\n"
    info += f"🔗 **Username:** {username}\n"
    return info

def get_main_keyboard():
    """Create main inline keyboard"""
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📌 Set Source Channel", callback_data="setup_source"),
        telebot.types.InlineKeyboardButton("📌 Set Destination Channel", callback_data="setup_dest"),
        telebot.types.InlineKeyboardButton("📊 View Settings", callback_data="setup_view"),
        telebot.types.InlineKeyboardButton("▶️ Start Auto-Forward", callback_data="setup_start"),
        telebot.types.InlineKeyboardButton("⏹ Stop Auto-Forward", callback_data="setup_stop")
    )
    return keyboard

# ==================== COMMAND HANDLERS ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    
    welcome_text = """
🤖 **Channel Auto-Forward Bot**

ဒီ Bot က Source Channel မှာ Video တက်တာနဲ့ Destination Channel ကို အလိုအလျောက် ပို့ပေးမှာပါ။

📌 **Commands:**
/setsource - Source Channel သတ်မှတ်ရန်
/setdestination - Destination Channel သတ်မှတ်ရန်
/status - လက်ရှိ Setting များကြည့်ရန်
/startforward - Auto-Forward စတင်ရန်
/stopforward - Auto-Forward ရပ်ရန်
/setup - Inline Keyboard ဖွင့်ရန်
/cancel - လုပ်ဆောင်ချက် ဖျက်သိမ်းရန်

📌 **အသုံးပြုပုံ:**
1. /setsource ပို့ပြီး Source Channel ID ထည့်ပါ
2. /setdestination ပို့ပြီး Destination Channel ID ထည့်ပါ
3. /startforward ပို့ပြီး စတင်ပါ
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['cancel'])
def cancel_action(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    bot.reply_to(message, "✅ လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းလိုက်ပါပြီ။")

@bot.message_handler(commands=['setsource'])
def set_source_command(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    
    user_states[user_id] = STATE_WAITING_FOR_SOURCE
    user_timeout[user_id] = datetime.now()
    
    reply_text = """
📌 **Source Channel ID ကို ထည့်ပါ။**

Channel ID ကို ဘယ်လိုရှာမလဲ?
1. ဒီ Bot ကို သင့် Channel မှာ Admin ထည့်ပါ။
2. Channel ထဲမှာ /start ပို့ပါ။
3. Bot က ID ကို ပြန်ပြောပါလိမ့်မယ်။

⏳ အချိန် ၅ မိနစ်အတွင်း ထည့်ပေးပါ။
❌ ဖျက်သိမ်းရန် /cancel ပို့ပါ။
"""
    bot.reply_to(message, reply_text)

@bot.message_handler(commands=['setdestination'])
def set_destination_command(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    
    user_states[user_id] = STATE_WAITING_FOR_DESTINATION
    user_timeout[user_id] = datetime.now()
    
    reply_text = """
📌 **Destination Channel ID ကို ထည့်ပါ။**

Channel ID ကို ဘယ်လိုရှာမလဲ?
1. ဒီ Bot ကို သင့် Channel မှာ Admin ထည့်ပါ။
2. Channel ထဲမှာ /start ပို့ပါ။
3. Bot က ID ကို ပြန်ပြောပါလိမ့်မယ်။

⏳ အချိန် ၅ မိနစ်အတွင်း ထည့်ပေးပါ။
❌ ဖျက်သိမ်းရန် /cancel ပို့ပါ။
"""
    bot.reply_to(message, reply_text)

@bot.message_handler(commands=['setup'])
def setup_command(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    bot.reply_to(message, "📌 **ရွေးချယ်ပါ။**", reply_markup=get_main_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_command(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    
    data = user_data.get(user_id, {})
    source = data.get('source', None)
    destination = data.get('destination', None)
    forwarding = data.get('forwarding', False)
    
    status_text = "📊 **လက်ရှိ Setting များ**\n\n"
    
    if source:
        try:
            chat = bot.get_chat(source)
            status_text += f"📌 **Source Channel:** {chat.title}\n"
            status_text += f"🆔 **ID:** `{source}`\n"
        except:
            status_text += f"📌 **Source Channel:** ❌ မရှိတော့ပါ\n"
    else:
        status_text += "📌 **Source Channel:** ❌ မသတ်မှတ်ရသေးပါ\n"
    
    if destination:
        try:
            chat = bot.get_chat(destination)
            status_text += f"📌 **Destination Channel:** {chat.title}\n"
            status_text += f"🆔 **ID:** `{destination}`\n"
        except:
            status_text += f"📌 **Destination Channel:** ❌ မရှိတော့ပါ\n"
    else:
        status_text += "📌 **Destination Channel:** ❌ မသတ်မှတ်ရသေးပါ\n"
    
    status_text += f"\n🔄 **Auto-Forward:** {'✅ ON' if forwarding else '❌ OFF'}"
    
    bot.reply_to(message, status_text, parse_mode='Markdown')

@bot.message_handler(commands=['startforward'])
def start_forward(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    
    data = user_data.get(user_id, {})
    
    if not data.get('source'):
        bot.reply_to(message, "❌ Source Channel မသတ်မှတ်ရသေးပါ။ /setsource နဲ့ သတ်မှတ်ပါ။")
        return
    
    if not data.get('destination'):
        bot.reply_to(message, "❌ Destination Channel မသတ်မှတ်ရသေးပါ။ /setdestination နဲ့ သတ်မှတ်ပါ။")
        return
    
    # Check if bot is still admin in both channels
    source_ok, source_title, _, _, _ = check_admin_status(data['source'])
    dest_ok, dest_title, _, _, _ = check_admin_status(data['destination'])
    
    if not source_ok:
        bot.reply_to(message, f"❌ Source Channel (`{data['source']}`) မှာ Admin မဖြစ်တော့ပါဘူး။ ပြန်စစ်ပါ။", parse_mode='Markdown')
        return
    
    if not dest_ok:
        bot.reply_to(message, f"❌ Destination Channel (`{data['destination']}`) မှာ Admin မဖြစ်တော့ပါဘူး။ ပြန်စစ်ပါ။", parse_mode='Markdown')
        return
    
    data['forwarding'] = True
    user_data[user_id] = data
    
    bot.reply_to(message, f"✅ **Auto-Forward ကို စတင်လိုက်ပါပြီ။**\n\n📌 Source: {source_title}\n📌 Destination: {dest_title}\n\nSource Channel မှာ Video တက်တာနဲ့ Destination Channel ကို ပို့ပေးပါ့မယ်။", parse_mode='Markdown')

@bot.message_handler(commands=['stopforward'])
def stop_forward(message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    
    data = user_data.get(user_id, {})
    data['forwarding'] = False
    user_data[user_id] = data
    
    bot.reply_to(message, "⏹ **Auto-Forward ကို ရပ်လိုက်ပါပြီ။**", parse_mode='Markdown')

# ==================== CHANNEL ID HANDLERS ====================

@bot.message_handler(func=lambda message: message.chat.type in ['channel', 'group', 'supergroup'] and message.text == '/start')
def handle_channel_start(message):
    chat_id = message.chat.id
    chat_title = message.chat.title
    
    # Check if bot is admin
    is_admin, title, members, chat_type, username = check_admin_status(chat_id)
    
    if is_admin:
        reply = f"✅ **ဒီ Channel ရဲ့ ID က:**\n`{chat_id}`\n\n"
        reply += format_channel_info(title, members, chat_type, username)
        reply += "\n📌 Source/Destination Channel အဖြစ် သတ်မှတ်ချင်ရင် /setsource သို့မဟုတ် /setdestination ကို သုံးပါ။"
    else:
        reply = f"❌ **ဒီ Channel မှာ Admin မဖြစ်ပါဘူး။**\n\n"
        reply += f"📌 **Channel ID:** `{chat_id}`\n"
        reply += f"📌 **Channel Name:** {chat_title}\n\n"
        reply += "⚠️ Bot ကို Admin အနေနဲ့ ထည့်ပြီးမှ ပြန်ကြိုးစားပါ။"
    
    bot.reply_to(message, reply, parse_mode='Markdown')

# ==================== MESSAGE HANDLERS FOR STATES ====================

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == STATE_WAITING_FOR_SOURCE)
def handle_source_id(message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Check timeout
    if user_id in user_timeout:
        if datetime.now() - user_timeout[user_id] > timedelta(minutes=5):
            reset_user_state(user_id)
            bot.reply_to(message, "⏰ အချိန်ကုန်သွားပါပြီ။ ပြန်ကြိုးစားပါ။ /setsource")
            return
    
    # Check if it's a valid channel ID
    if not is_channel_id(text):
        bot.reply_to(message, "❌ **မှားယွင်းနေပါတယ်။**\nChannel ID ကို ထည့်ပါ။ (ဥပမာ: -1001234567890)\n\n/cancel ပို့ပြီး ဖျက်သိမ်းနိုင်ပါတယ်။")
        return
    
    channel_id = get_channel_id_from_text(text)
    
    # Check if bot is admin
    is_admin, title, members_count, chat_type, username = check_admin_status(channel_id)
    
    if is_admin:
        # Save source channel
        data = user_data.get(user_id, {})
        data['source'] = channel_id
        user_data[user_id] = data
        
        reply = "✅ **Source Channel ကို အောင်မြင်စွာ သတ်မှတ်ပြီးပါပြီ။**\n\n"
        reply += format_channel_info(title, members_count, chat_type, username)
        reply += "\n📌 ဆက်လက်လုပ်ဆောင်ရန် /setup ကို သုံးပါ။"
        
        bot.reply_to(message, reply, parse_mode='Markdown')
        reset_user_state(user_id)
    else:
        reply = "❌ **Admin မဖြစ်ပါဘူး။**\n\n"
        reply += f"📌 **Channel ID:** `{channel_id}`\n"
        if title:
            reply += f"📌 **Channel Name:** {title}\n"
        reply += "\n⚠️ ဒီ Channel မှာ Bot ကို Admin အနေနဲ့ ထည့်ပေးပါ။\n"
        reply += "Admin ထည့်ပြီးရင် ပြန်ကြိုးစားပါ။\n\n"
        reply += "/cancel ပို့ပြီး ဖျက်သိမ်းနိုင်ပါတယ်။"
        
        bot.reply_to(message, reply, parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == STATE_WAITING_FOR_DESTINATION)
def handle_destination_id(message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Check timeout
    if user_id in user_timeout:
        if datetime.now() - user_timeout[user_id] > timedelta(minutes=5):
            reset_user_state(user_id)
            bot.reply_to(message, "⏰ အချိန်ကုန်သွားပါပြီ။ ပြန်ကြိုးစားပါ။ /setdestination")
            return
    
    # Check if it's a valid channel ID
    if not is_channel_id(text):
        bot.reply_to(message, "❌ **မှားယွင်းနေပါတယ်။**\nChannel ID ကို ထည့်ပါ။ (ဥပမာ: -1001234567890)\n\n/cancel ပို့ပြီး ဖျက်သိမ်းနိုင်ပါတယ်။")
        return
    
    channel_id = get_channel_id_from_text(text)
    
    # Check if bot is admin
    is_admin, title, members_count, chat_type, username = check_admin_status(channel_id)
    
    if is_admin:
        # Save destination channel
        data = user_data.get(user_id, {})
        data['destination'] = channel_id
        user_data[user_id] = data
        
        reply = "✅ **Destination Channel ကို အောင်မြင်စွာ သတ်မှတ်ပြီးပါပြီ။**\n\n"
        reply += format_channel_info(title, members_count, chat_type, username)
        reply += "\n📌 ဆက်လက်လုပ်ဆောင်ရန် /setup ကို သုံးပါ။"
        
        bot.reply_to(message, reply, parse_mode='Markdown')
        reset_user_state(user_id)
    else:
        reply = "❌ **Admin မဖြစ်ပါဘူး။**\n\n"
        reply += f"📌 **Channel ID:** `{channel_id}`\n"
        if title:
            reply += f"📌 **Channel Name:** {title}\n"
        reply += "\n⚠️ ဒီ Channel မှာ Bot ကို Admin အနေနဲ့ ထည့်ပေးပါ။\n"
        reply += "Admin ထည့်ပြီးရင် ပြန်ကြိုးစားပါ။\n\n"
        reply += "/cancel ပို့ပြီး ဖျက်သိမ်းနိုင်ပါတယ်။"
        
        bot.reply_to(message, reply, parse_mode='Markdown')

# ==================== CALLBACK HANDLERS ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith('setup_'))
def handle_setup_callback(call):
    user_id = call.from_user.id
    action = call.data.replace('setup_', '')
    
    if action == 'source':
        bot.answer_callback_query(call.id)
        set_source_command(call.message)
        
    elif action == 'dest':
        bot.answer_callback_query(call.id)
        set_destination_command(call.message)
        
    elif action == 'view':
        bot.answer_callback_query(call.id)
        status_command(call.message)
        
    elif action == 'start':
        bot.answer_callback_query(call.id)
        start_forward(call.message)
        
    elif action == 'stop':
        bot.answer_callback_query(call.id)
        stop_forward(call.message)

# ==================== AUTO-FORWARD LOGIC ====================

@bot.channel_post_handler(func=lambda message: True)
def handle_channel_post(message):
    """Handle new posts in channels"""
    # Check if message is from a channel
    if message.chat.type not in ['channel']:
        return
    
    chat_id = message.chat.id
    
    # Find users who have this channel as source
    for user_id, data in user_data.items():
        if data.get('source') == chat_id and data.get('forwarding', False):
            dest_id = data.get('destination')
            if dest_id:
                try:
                    # Check if message is video
                    if message.video:
                        # Copy video with caption
                        bot.copy_message(
                            chat_id=dest_id,
                            from_chat_id=chat_id,
                            message_id=message.message_id,
                            caption=message.caption if message.caption else None
                        )
                        print(f"✅ Video copied from {chat_id} to {dest_id}")
                    else:
                        # Only copy video messages (skip others)
                        pass
                except Exception as e:
                    print(f"❌ Error copying message: {e}")

# ==================== MAIN ====================

print("=" * 50)
print("🤖 Channel Auto-Forward Bot")
print("=" * 50)
print(f"📌 Bot Username: @{bot.get_me().username}")
print("📌 Bot is running. Press Ctrl+C to stop.")
print("=" * 50)

try:
    # Use polling with error handling
    bot.polling(none_stop=True, interval=1, timeout=30)
except KeyboardInterrupt:
    print("\n👋 Bot stopped.")
except Exception as e:
    print(f"❌ Error: {e}")
