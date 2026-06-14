# main.py
import random
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from game_data import *

TOKEN = "8110472217:AAH7TRTi2N1bfz4Oy5-bEiUIoxPStdJVMpQ"

IMAGES_PATH = "images/"

# ========== أعداء الكمبيوتر ==========
BOT_ENEMIES = [
    {'name': 'غول صغير', 'power_mult': 0.7},
    {'name': 'ذئب بري', 'power_mult': 0.8},
    {'name': 'لص', 'power_mult': 0.9},
    {'name': 'محارب مظلم', 'power_mult': 1.0},
    {'name': 'فارس', 'power_mult': 1.1},
]

# تخزين مهام البحث
search_tasks = {}

# ========== القائمة الرئيسية ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    
    if not get_player(user_id):
        create_player(user_id, name)
    
    player = get_player(user_id)
    
    keyboard = [
        [InlineKeyboardButton("⚔️ قتال", callback_data='fight')],
        [InlineKeyboardButton("🏋️ تدريب", callback_data='train')],
        [InlineKeyboardButton("📊 معلوماتي", callback_data='stats')],
        [InlineKeyboardButton("🛒 المتجر", callback_data='shop')],
        [InlineKeyboardButton("🎁 صندوق الكنز", callback_data='chest')],
        [InlineKeyboardButton("🏆 متصدرين", callback_data='leaderboard')]
    ]
    
    warrior_image = os.path.join(IMAGES_PATH, "warrior_base.png")
    
    msg = f"🌟 *مرحباً أيها المحارب {name}!* 🌟\n\n"
    msg += f"🏆 نقاط التصنيف (ELO): {player['elo']}\n"
    msg += f"🍀 عامل الحظ: +{player['luck']}\n"
    msg += f"🏅 فوز أونلاين: {player['online_wins']} (كل 10 فوز = مستوى)\n\n"
    msg += f"اختر مغامرتك:"
    
    if os.path.exists(warrior_image):
        with open(warrior_image, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=msg,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ========== زر القتال الموحد ==========
async def fight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    # التحقق من فترة التهدئة
    remaining = get_waiting_time(user_id)
    if remaining > 0:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
        await query.message.reply_text(
            f"⏳ *يجب الانتظار {remaining} ثانية قبل القتال مرة أخرى!*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.delete_message()
        return
    
    # إضافة اللاعب لقائمة الانتظار
    add_to_waiting_queue(user_id)
    
    # رسالة بحث عن خصم
    keyboard = [[InlineKeyboardButton("❌ إلغاء البحث", callback_data='cancel_search')]]
    
    msg = f"🔍 *جاري البحث عن خصم...*\n\n"
    msg += f"⏳ لديك 10 ثواني للعثور على خصم حقيقي\n"
    msg += f"👾 إذا لم يتم العثور على خصم، ستقاتل الكمبيوتر\n\n"
    msg += f"*ملاحظة:* قتال الكمبيوتر يعطي مكافآت أقل!"
    
    search_msg = await query.message.reply_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    await query.delete_message()
    
    # بدء مهمة البحث
    task = asyncio.create_task(search_for_opponent(update, context, user_id, search_msg.chat_id, search_msg.message_id))
    search_tasks[user_id] = task

# ========== البحث عن خصم (مدة 10 ثواني) ==========
async def search_for_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, chat_id, message_id):
    """البحث عن خصم لمدة 10 ثواني، إذا لم يوجد يبدأ قتال مع الكمبيوتر"""
    await asyncio.sleep(10)
    
    # إزالة المهمة من القاموس
    if user_id in search_tasks:
        del search_tasks[user_id]
    
    # التحقق من وجود خصم
    opponent_id = find_match(user_id)
    
    if opponent_id:
        # تم العثور على خصم حقيقي
        remove_from_waiting_queue(user_id)
        remove_from_waiting_queue(opponent_id)
        
        # إنشاء مباراة جديدة
        fight_id = create_fight(user_id, opponent_id)
        
        # إعلام الطرفين
        player = get_player(user_id)
        opponent = get_player(opponent_id)
        
        msg = f"🎯 *تم العثور على خصم حقيقي!*\n\n"
        msg += f"👤 أنت: {player['name']} (قوة: {get_total_power(user_id)})\n"
        msg += f"👤 الخصم: {opponent['name']} (قوة: {get_total_power(opponent_id)})\n\n"
        msg += f"⚔️ *المعركة تبدأ خلال 10 ثواني!*"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
        
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=msg,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass
        
        # بدء الموقت
        asyncio.create_task(pvp_timer(update, context, fight_id, user_id, opponent_id))
        
    else:
        # لم يتم العثور على خصم → قتال ضد الكمبيوتر
        remove_from_waiting_queue(user_id)
        
        await bot_fight_after_search(update, context, user_id, chat_id, message_id)

# ========== قتال ضد الكمبيوتر (بعد البحث الفاشل) ==========
async def bot_fight_after_search(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, chat_id, message_id):
    """قتال ضد الكمبيوتر بعد 10 ثواني من البحث"""
    player = get_player(user_id)
    player_power = get_total_power(user_id)
    
    # اختيار عدو عشوائي
    enemy = random.choice(BOT_ENEMIES)
    enemy_power = int(player_power * enemy['power_mult'])
    enemy_name = enemy['name']
    
    # حساب النتيجة مع عامل الحظ
    luck = player['luck']
    result = calculate_fight_winner(player_power, enemy_power, luck)
    
    set_fight_cooldown(user_id)
    
    if result == 'player':
        # فوز ضد الكمبيوتر (مكافآت قليلة)
        xp_gain = random.randint(10, 25)
        coin_gain = random.randint(5, 15)
        level_up, consecutive = add_win(user_id, xp_gain, coin_gain, is_online=False)
        
        msg = f"👾 *لم يتم العثور على خصم حقيقي!*\n\n"
        msg += f"⚔️ *قتال ضد {enemy_name}!* ⚔️\n\n"
        msg += f"⚔️ قوتك: {player_power} + ({luck} حظ)\n"
        msg += f"👾 قوة العدو: {enemy_power}\n\n"
        msg += f"🎉 *فوز!* 🎉\n"
        msg += f"✨ +{xp_gain} XP | +{coin_gain} عملة (مكافآت أقل لقتال الكمبيوتر)\n"
        
        if level_up:
            new_player = get_player(user_id)
            msg += f"\n🎉 *تهانينا! وصلت للمستوى {new_player['level']}!*"
    else:
        # خسارة ضد الكمبيوتر (خصم بسيط)
        xp_gain = random.randint(3, 8)
        add_loss(user_id, xp_gain)
        
        # خسارة نقاط هجوم ودفاع بسيطة
        new_attack = max(5, player['attack'] - random.randint(1, 2))
        new_defense = max(5, player['defense'] - random.randint(1, 2))
        cursor.execute('UPDATE players SET attack = ?, defense = ? WHERE user_id = ?',
                       (new_attack, new_defense, user_id))
        conn.commit()
        
        msg = f"👾 *لم يتم العثور على خصم حقيقي!*\n\n"
        msg += f"⚔️ *قتال ضد {enemy_name}!* ⚔️\n\n"
        msg += f"⚔️ قوتك: {player_power} + ({luck} حظ)\n"
        msg += f"👾 قوة العدو: {enemy_power}\n\n"
        msg += f"💀 *هزيمة!* 💀\n"
        msg += f"✨ +{xp_gain} XP\n"
        msg += f"📉 خسرت نقطتي هجوم ودفاع"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        pass

# ========== مؤقت القتال PvP ==========
async def pvp_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, fight_id, player1_id, player2_id):
    """مؤقت 10 ثواني للقتال"""
    await asyncio.sleep(10)
    
    fight = get_fight(fight_id)
    if not fight or fight['status'] != 'active':
        return
    
    player1 = get_player(player1_id)
    player2 = get_player(player2_id)
    player1_power = get_total_power(player1_id)
    player2_power = get_total_power(player2_id)
    luck1 = player1['luck']
    luck2 = player2['luck']
    
    # حساب النتيجة مع عامل الحظ
    final_power1 = player1_power + luck1
    final_power2 = player2_power + luck2
    
    if final_power1 >= final_power2:
        winner_id = player1_id
        loser_id = player2_id
    else:
        winner_id = player2_id
        loser_id = player1_id
    
    # إنهاء المباراة
    end_fight(fight_id, winner_id, loser_id, is_online=True)
    set_fight_cooldown(player1_id)
    set_fight_cooldown(player2_id)
    
    winner = get_player(winner_id)
    loser = get_player(loser_id)
    
    # إرسال النتيجة
    result_msg = f"⚔️ *نتيجة المعركة!*\n\n"
    result_msg += f"🏆 *الفائز: {winner['name']}*\n"
    result_msg += f"💀 *الخاسر: {loser['name']}*\n\n"
    result_msg += f"✨ *التغييرات:*\n"
    result_msg += f"📈 +25 نقطة ELO | +XP | +عملات\n"
    result_msg += f"📉 -25 نقطة ELO | -نقاط هجوم ودفاع\n\n"
    result_msg += f"🍀 عامل الحظ للفائز: +{winner['luck']}"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(chat_id=player1_id, text=result_msg, parse_mode='Markdown', reply_markup=reply_markup)
        await context.bot.send_message(chat_id=player2_id, text=result_msg, parse_mode='Markdown', reply_markup=reply_markup)
    except:
        pass

# ========== إلغاء البحث ==========
async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    # إلغاء مهمة البحث
    if user_id in search_tasks:
        search_tasks[user_id].cancel()
        del search_tasks[user_id]
    
    remove_from_waiting_queue(user_id)
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
    await query.edit_message_text(
        "✅ *تم إلغاء البحث عن خصم*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== نظام التدريب ==========
async def train_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if can_train(user_id):
        do_train(user_id)
        player = get_player(user_id)
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
        await query.message.reply_text(
            f"🏋️ *تدريب ناجح!*\n\n"
            f"⚔️ هجومك الآن: {player['attack']}\n"
            f"🛡️ دفاعك الآن: {player['defense']}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        player = get_player(user_id)
        last = datetime.fromisoformat(player['last_train'])
        remaining = timedelta(hours=3) - (datetime.now() - last)
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
        await query.message.reply_text(
            f"⏳ *يجب الانتظار {hours} ساعة و {minutes} دقيقة للتدريب مرة أخرى*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    await query.delete_message()

# ========== عرض المعلومات ==========
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    player = get_player(user_id)
    
    msg = f"📊 *{player['name']}*\n\n"
    msg += f"🏆 نقاط ELO: {player['elo']}\n"
    msg += f"🍀 عامل الحظ: +{player['luck']}\n"
    msg += f"🏅 فوز أونلاين: {player['online_wins']}\n"
    msg += f"🏅 المستوى: {player['level']}\n"
    msg += f"⭐ XP: {player['xp']}/{player['xp_to_next']}\n"
    msg += f"💰 العملات: {player['coins']}\n"
    msg += f"⚔️ الفوز: {player['wins']} | 💀 الخسارة: {player['losses']}\n"
    msg += f"🔥 سلسلة انتصارات: {player['consecutive_wins']}\n"
    msg += f"🔑 المفاتيح: {player['keys_collected']}\n\n"
    msg += f"⚔️ الهجوم: {get_total_attack(user_id)}\n"
    msg += f"🛡️ الدفاع: {get_total_defense(user_id)}\n\n"
    msg += f"🗡️ السلاح: {player['weapon']}\n"
    msg += f"🛡️ الدرع: {player['armor']}"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
    
    warrior_image = os.path.join(IMAGES_PATH, "warrior_base.png")
    
    if os.path.exists(warrior_image):
        with open(warrior_image, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=msg,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    await query.delete_message()

# ========== المتجر ==========
async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    player = get_player(user_id)
    
    cursor.execute('SELECT * FROM weapons ORDER BY required_level')
    weapons = cursor.fetchall()
    
    text = f"💰 *عملاتك: {player['coins']}*\n\n🗡️ *الأسلحة:*\n"
    buttons = []
    
    for w in weapons:
        w_name, w_attack, w_price, w_level, w_img = w
        if w_level <= player['level']:
            if w_name != player['weapon']:
                buttons.append([InlineKeyboardButton(f"شراء {w_name} ({w_price}💰)", callback_data=f'buy_weapon_{w_name}')])
            text += f"✅ {w_name}: +{w_attack} هجوم | {w_price}💰\n"
        else:
            text += f"🔒 {w_name}: المستوى {w_level}\n"
    
    cursor.execute('SELECT * FROM armor ORDER BY required_level')
    armors = cursor.fetchall()
    
    text += "\n🛡️ *الدروع:*\n"
    for a in armors:
        a_name, a_defense, a_price, a_level, a_img = a
        if a_level <= player['level']:
            if a_name != player['armor']:
                buttons.append([InlineKeyboardButton(f"شراء {a_name} ({a_price}💰)", callback_data=f'buy_armor_{a_name}')])
            text += f"✅ {a_name}: +{a_defense} دفاع | {a_price}💰\n"
        else:
            text += f"🔒 {a_name}: المستوى {a_level}\n"
    
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')])
    
    shop_image = os.path.join(IMAGES_PATH, "shop_background.png")
    
    if os.path.exists(shop_image):
        with open(shop_image, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    else:
        await query.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    
    await query.delete_message()

# ========== صندوق الكنز ==========
async def chest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    player = get_player(user_id)
    
    if player['keys_collected'] >= 3:
        new_keys = player['keys_collected'] - 3
        cursor.execute('UPDATE players SET keys_collected = ? WHERE user_id = ?', (new_keys, user_id))
        
        reward_type = random.choice(['coins', 'weapon', 'armor', 'xp'])
        
        if reward_type == 'coins':
            reward = random.randint(50, 200)
            new_coins = player['coins'] + reward
            cursor.execute('UPDATE players SET coins = ? WHERE user_id = ?', (new_coins, user_id))
            conn.commit()
            msg = f"🎁 *فتحت الصندوق!*\n\n💰 حصلت على {reward} عملة!"
        
        elif reward_type == 'xp':
            reward = random.randint(25, 100)
            add_xp(user_id, reward)
            msg = f"🎁 *فتحت الصندوق!*\n\n⭐ حصلت على {reward} XP!"
        
        elif reward_type == 'weapon':
            cursor.execute('SELECT name FROM weapons WHERE required_level <= ? AND name != ? ORDER BY RANDOM() LIMIT 1',
                          (player['level'], player['weapon']))
            weapon = cursor.fetchone()
            if weapon:
                cursor.execute('UPDATE players SET weapon = ? WHERE user_id = ?', (weapon[0], user_id))
                conn.commit()
                msg = f"🎁 *فتحت الصندوق!*\n\n🗡️ حصلت على سلاح نادر: {weapon[0]}!"
            else:
                msg = "🎁 الصندوق فارغ... جرب مرة أخرى!"
        
        else:
            cursor.execute('SELECT name FROM armor WHERE required_level <= ? AND name != ? ORDER BY RANDOM() LIMIT 1',
                          (player['level'], player['armor']))
            armor = cursor.fetchone()
            if armor:
                cursor.execute('UPDATE players SET armor = ? WHERE user_id = ?', (armor[0], user_id))
                conn.commit()
                msg = f"🎁 *فتحت الصندوق!*\n\n🛡️ حصلت على درع نادر: {armor[0]}!"
            else:
                msg = "🎁 الصندوق فارغ... جرب مرة أخرى!"
    else:
        msg = f"🔒 *تحتاج 3 مفاتيح لفتح الصندوق!*\n\n🔑 لديك {player['keys_collected']}/3 مفاتيح\n\n💡 احصل على المفاتيح بـ 3 انتصارات متتالية!"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
    await query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    await query.delete_message()

# ========== المشتريات ==========
async def buy_weapon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, weapon_name):
    query = update.callback_query
    user_id = query.from_user.id
    player = get_player(user_id)
    
    cursor.execute('SELECT * FROM weapons WHERE name = ?', (weapon_name,))
    weapon = cursor.fetchone()
    
    if not weapon:
        await query.answer("السلاح غير موجود!")
        return
    
    if player['coins'] < weapon[2]:
        await query.answer("❌ عملاتك لا تكفي!")
        return
    
    if weapon[3] > player['level']:
        await query.answer(f"🔒 تحتاج المستوى {weapon[3]}!")
        return
    
    new_coins = player['coins'] - weapon[2]
    cursor.execute('UPDATE players SET coins = ?, weapon = ? WHERE user_id = ?', 
                   (new_coins, weapon_name, user_id))
    conn.commit()
    
    await query.answer(f"✅ تم شراء {weapon_name}!")
    await shop_cmd(update, context)

async def buy_armor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, armor_name):
    query = update.callback_query
    user_id = query.from_user.id
    player = get_player(user_id)
    
    cursor.execute('SELECT * FROM armor WHERE name = ?', (armor_name,))
    armor = cursor.fetchone()
    
    if not armor:
        await query.answer("الدرع غير موجود!")
        return
    
    if player['coins'] < armor[2]:
        await query.answer("❌ عملاتك لا تكفي!")
        return
    
    if armor[3] > player['level']:
        await query.answer(f"🔒 تحتاج المستوى {armor[3]}!")
        return
    
    new_coins = player['coins'] - armor[2]
    cursor.execute('UPDATE players SET coins = ?, armor = ? WHERE user_id = ?', 
                   (new_coins, armor_name, user_id))
    conn.commit()
    
    await query.answer(f"✅ تم شراء {armor_name}!")
    await shop_cmd(update, context)

# ========== متصدرين ==========
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute('''
    SELECT name, level, wins, elo, online_wins, luck
    FROM players ORDER BY elo DESC LIMIT 10
    ''')
    top_players = cursor.fetchall()
    
    if not top_players:
        msg = "لا يوجد لاعبين بعد!"
    else:
        msg = "🏆 *قائمة التصنيف (ELO)* 🏆\n\n"
        for i, p in enumerate(top_players, 1):
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            msg += f"{medal} {p[0]} - {p[3]} نقطة | المستوى {p[1]} | {p[2]} فوز | 🍀+{p[5]}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_menu')]]
    await query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    await query.delete_message()

# ========== الرجوع للقائمة ==========
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    name = query.from_user.first_name
    player = get_player(user_id)
    
    keyboard = [
        [InlineKeyboardButton("⚔️ قتال", callback_data='fight')],
        [InlineKeyboardButton("🏋️ تدريب", callback_data='train')],
        [InlineKeyboardButton("📊 معلوماتي", callback_data='stats')],
        [InlineKeyboardButton("🛒 المتجر", callback_data='shop')],
        [InlineKeyboardButton("🎁 صندوق الكنز", callback_data='chest')],
        [InlineKeyboardButton("🏆 متصدرين", callback_data='leaderboard')]
    ]
    
    warrior_image = os.path.join(IMAGES_PATH, "warrior_base.png")
    
    msg = f"🌟 *مرحباً بعودتك {name}!* 🌟\n\n🏆 ELO: {player['elo']} | 🍀 حظ: +{player['luck']}\n\nاختر مغامرتك:"
    
    if os.path.exists(warrior_image):
        with open(warrior_image, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=msg,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    await query.delete_message()

# ========== معالج الأزرار ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'fight':
        await fight(update, context)
    elif data == 'train':
        await train_cmd(update, context)
    elif data == 'stats':
        await stats_cmd(update, context)
    elif data == 'shop':
        await shop_cmd(update, context)
    elif data == 'chest':
        await chest_cmd(update, context)
    elif data == 'leaderboard':
        await leaderboard_cmd(update, context)
    elif data == 'cancel_search':
        await cancel_search(update, context)
    elif data == 'back_to_menu':
        await back_to_menu(update, context)
    elif data.startswith('buy_weapon_'):
        weapon_name = data.replace('buy_weapon_', '')
        await buy_weapon_cmd(update, context, weapon_name)
    elif data.startswith('buy_armor_'):
        armor_name = data.replace('buy_armor_', '')
        await buy_armor_cmd(update, context, armor_name)

# ========== تشغيل البوت ==========
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("⚔️ البوت شغال...")
    # زيادة وقت المهلة
    app.run_polling(read_timeout=60, write_timeout=60, connect_timeout=60)

if __name__ == "__main__":
    main()
