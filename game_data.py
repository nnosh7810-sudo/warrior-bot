# game_data.py
import sqlite3
import random
from datetime import datetime, timedelta

conn = sqlite3.connect('warrior_game.db', check_same_thread=False)
cursor = conn.cursor()

# ========== حذف الجداول القديمة وإعادة إنشائها ==========
cursor.execute('DROP TABLE IF EXISTS players')
cursor.execute('DROP TABLE IF EXISTS weapons')
cursor.execute('DROP TABLE IF EXISTS armor')
cursor.execute('DROP TABLE IF EXISTS waiting_players')
cursor.execute('DROP TABLE IF EXISTS active_fights')
cursor.execute('DROP TABLE IF EXISTS fight_cooldown')

# ========== إنشاء الجداول من جديد ==========
cursor.execute('''
CREATE TABLE players (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    level INTEGER DEFAULT 1,
    xp INTEGER DEFAULT 0,
    xp_to_next INTEGER DEFAULT 100,
    attack INTEGER DEFAULT 10,
    defense INTEGER DEFAULT 10,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    consecutive_wins INTEGER DEFAULT 0,
    keys_collected INTEGER DEFAULT 0,
    coins INTEGER DEFAULT 50,
    weapon TEXT DEFAULT 'سيف خشبي',
    armor TEXT DEFAULT 'درع جلدي',
    skin TEXT DEFAULT 'مبتدئ',
    last_train DATETIME,
    elo INTEGER DEFAULT 1000,
    luck INTEGER DEFAULT 0,          -- عامل الحظ (يزيد كل 5 فوز)
    online_wins INTEGER DEFAULT 0    -- عدد مرات الفوز أونلاين (لتسوية المستوى)
)
''')

cursor.execute('''
CREATE TABLE weapons (
    name TEXT PRIMARY KEY,
    attack_bonus INTEGER,
    price INTEGER,
    required_level INTEGER,
    image TEXT
)
''')

cursor.execute('''
CREATE TABLE armor (
    name TEXT PRIMARY KEY,
    defense_bonus INTEGER,
    price INTEGER,
    required_level INTEGER,
    image TEXT
)
''')

cursor.execute('''
CREATE TABLE waiting_players (
    user_id INTEGER PRIMARY KEY,
    search_time DATETIME
)
''')

cursor.execute('''
CREATE TABLE active_fights (
    fight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player1_id INTEGER,
    player2_id INTEGER,
    start_time DATETIME,
    status TEXT DEFAULT 'active'
)
''')

cursor.execute('''
CREATE TABLE fight_cooldown (
    user_id INTEGER PRIMARY KEY,
    last_fight_time DATETIME
)
''')

# ========== إضافة الأسلحة (أسعار أعلى) ==========
weapons_data = [
    ('سيف خشبي', 5, 0, 1, 'weapon_wooden.png'),
    ('سيف حديدي', 12, 150, 2, 'weapon_iron.png'),      # سعر أعلى
    ('سيف ذهبي', 20, 350, 4, 'weapon_golden.png'),     # سعر أعلى
    ('سيف ناري', 35, 700, 6, 'weapon_fire.png'),       # سعر أعلى
    ('سيف أسطوري', 55, 1500, 10, 'weapon_legendary.png') # سعر أعلى
]

armor_data = [
    ('درع جلدي', 5, 0, 1, 'armor_leather.png'),
    ('درع حديدي', 12, 150, 2, 'armor_iron.png'),       # سعر أعلى
    ('درع فضي', 20, 350, 4, 'armor_silver.png'),       # سعر أعلى
    ('درع ذهبي', 35, 700, 6, 'armor_golden.png'),      # سعر أعلى
    ('درع أسطوري', 55, 1500, 10, 'armor_legendary.png') # سعر أعلى
]

for w in weapons_data:
    cursor.execute('INSERT OR IGNORE INTO weapons (name, attack_bonus, price, required_level, image) VALUES (?, ?, ?, ?, ?)', w)

for a in armor_data:
    cursor.execute('INSERT OR IGNORE INTO armor (name, defense_bonus, price, required_level, image) VALUES (?, ?, ?, ?, ?)', a)

conn.commit()

# ========== دوال اللاعب الأساسية ==========
def get_player(user_id):
    cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        return {
            'user_id': row[0],
            'name': row[1],
            'level': row[2],
            'xp': row[3],
            'xp_to_next': row[4],
            'attack': row[5],
            'defense': row[6],
            'wins': row[7],
            'losses': row[8],
            'consecutive_wins': row[9],
            'keys_collected': row[10],
            'coins': row[11],
            'weapon': row[12],
            'armor': row[13],
            'skin': row[14],
            'last_train': row[15],
            'elo': row[16] if len(row) > 16 else 1000,
            'luck': row[17] if len(row) > 17 else 0,
            'online_wins': row[18] if len(row) > 18 else 0
        }
    return None

def create_player(user_id, name):
    now = datetime.now().isoformat()
    cursor.execute('''
    INSERT INTO players (user_id, name, last_train, elo, luck, online_wins) VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, name, now, 1000, 0, 0))
    conn.commit()

def get_total_attack(user_id):
    player = get_player(user_id)
    if not player:
        return 0
    cursor.execute('SELECT attack_bonus FROM weapons WHERE name = ?', (player['weapon'],))
    result = cursor.fetchone()
    weapon_bonus = result[0] if result else 5
    return player['attack'] + weapon_bonus

def get_total_defense(user_id):
    player = get_player(user_id)
    if not player:
        return 0
    cursor.execute('SELECT defense_bonus FROM armor WHERE name = ?', (player['armor'],))
    result = cursor.fetchone()
    armor_bonus = result[0] if result else 5
    return player['defense'] + armor_bonus

def get_total_power(user_id):
    return get_total_attack(user_id) + get_total_defense(user_id)

# ========== نظام الحظ ==========
def update_luck(user_id):
    """كل 5 فوز أونلاين يزيد عامل الحظ"""
    player = get_player(user_id)
    if player and player['online_wins'] > 0 and player['online_wins'] % 5 == 0:
        new_luck = player['luck'] + 1
        cursor.execute('UPDATE players SET luck = ? WHERE user_id = ?', (new_luck, user_id))
        conn.commit()
        return True
    return False

def check_level_up_by_wins(user_id):
    """كل 10 فوز أونلاين يزيد المستوى"""
    player = get_player(user_id)
    if player and player['online_wins'] >= 10:
        # حساب عدد مرات تسوية المستوى
        new_level = player['level'] + (player['online_wins'] // 10)
        cursor.execute('UPDATE players SET level = ? WHERE user_id = ?', (new_level, user_id))
        conn.commit()
        return True
    return False

# ========== نظام التدريب ==========
def can_train(user_id):
    player = get_player(user_id)
    if not player or not player['last_train']:
        return True
    last = datetime.fromisoformat(player['last_train'])
    return datetime.now() - last >= timedelta(hours=3)

def do_train(user_id):
    if not can_train(user_id):
        return False
    player = get_player(user_id)
    new_attack = player['attack'] + random.randint(2, 5)
    new_defense = player['defense'] + random.randint(2, 5)
    cursor.execute('UPDATE players SET attack = ?, defense = ?, last_train = ? WHERE user_id = ?',
                   (new_attack, new_defense, datetime.now().isoformat(), user_id))
    conn.commit()
    return True

# ========== نظام XP والمستويات ==========
def add_xp(user_id, amount):
    player = get_player(user_id)
    if not player:
        return False
    new_xp = player['xp'] + amount
    level_up = False
    xp_to_next = player['xp_to_next']
    level = player['level']
    coins = player['coins']
    
    while new_xp >= xp_to_next:
        new_xp -= xp_to_next
        level += 1
        xp_to_next = int(xp_to_next * 1.2)
        coins += level * 15  # مكافأة مستوى أقل
        level_up = True
    
    cursor.execute('UPDATE players SET xp = ?, level = ?, xp_to_next = ?, coins = ? WHERE user_id = ?',
                   (new_xp, level, xp_to_next, coins, user_id))
    conn.commit()
    return level_up

def add_win(user_id, xp_gain, coin_gain, is_online=True):
    player = get_player(user_id)
    if not player:
        return False, 0
    
    new_coins = player['coins'] + coin_gain
    new_wins = player['wins'] + 1
    new_consecutive = player['consecutive_wins'] + 1
    new_online_wins = player['online_wins'] + (1 if is_online else 0)
    
    cursor.execute('UPDATE players SET coins = ?, wins = ?, consecutive_wins = ?, online_wins = ? WHERE user_id = ?',
                   (new_coins, new_wins, new_consecutive, new_online_wins, user_id))
    conn.commit()
    
    level_up = add_xp(user_id, xp_gain)
    
    # تحديث الحظ والمستوى
    update_luck(user_id)
    check_level_up_by_wins(user_id)
    
    return level_up, new_consecutive

def add_loss(user_id, xp_gain):
    player = get_player(user_id)
    if not player:
        return
    new_losses = player['losses'] + 1
    cursor.execute('UPDATE players SET losses = ?, consecutive_wins = 0 WHERE user_id = ?',
                   (new_losses, user_id))
    conn.commit()
    add_xp(user_id, xp_gain)

def add_key(user_id):
    player = get_player(user_id)
    if not player:
        return 0
    new_keys = player['keys_collected'] + 1
    cursor.execute('UPDATE players SET keys_collected = ?, consecutive_wins = 0 WHERE user_id = ?',
                   (new_keys, user_id))
    conn.commit()
    return new_keys

# ========== نظام PvP والقتال ==========
def can_fight_now(user_id):
    """تتحقق إذا كان المستخدم يقدر يقتال (الـ 30 ثانية خلصت)"""
    cursor.execute('SELECT last_fight_time FROM fight_cooldown WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if not result:
        return True
    last_fight = datetime.fromisoformat(result[0])
    return datetime.now() - last_fight >= timedelta(seconds=30)

def set_fight_cooldown(user_id):
    """تسجيل وقت آخر قتال للمستخدم"""
    now = datetime.now().isoformat()
    cursor.execute('INSERT OR REPLACE INTO fight_cooldown (user_id, last_fight_time) VALUES (?, ?)',
                   (user_id, now))
    conn.commit()

def get_waiting_time(user_id):
    """وقت الانتظار المتبقي للقتال (بالثواني)"""
    cursor.execute('SELECT last_fight_time FROM fight_cooldown WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if not result:
        return 0
    last_fight = datetime.fromisoformat(result[0])
    elapsed = (datetime.now() - last_fight).total_seconds()
    remaining = 30 - elapsed
    return max(0, int(remaining))

def add_to_waiting_queue(user_id):
    """إضافة لاعب لقائمة الانتظار"""
    now = datetime.now().isoformat()
    cursor.execute('INSERT OR REPLACE INTO waiting_players (user_id, search_time) VALUES (?, ?)',
                   (user_id, now))
    conn.commit()

def remove_from_waiting_queue(user_id):
    """إزالة لاعب من قائمة الانتظار"""
    cursor.execute('DELETE FROM waiting_players WHERE user_id = ?', (user_id,))
    conn.commit()

def find_match(user_id):
    """البحث عن خصم مناسب"""
    cursor.execute('''
        SELECT user_id FROM waiting_players 
        WHERE user_id != ? 
        ORDER BY search_time ASC 
        LIMIT 1
    ''', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def create_fight(player1_id, player2_id):
    """إنشاء مباراة جديدة"""
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO active_fights (player1_id, player2_id, start_time) 
        VALUES (?, ?, ?)
    ''', (player1_id, player2_id, now))
    conn.commit()
    return cursor.lastrowid

def get_fight(fight_id):
    """الحصول على معلومات المباراة"""
    cursor.execute('SELECT * FROM active_fights WHERE fight_id = ?', (fight_id,))
    result = cursor.fetchone()
    if result:
        return {
            'fight_id': result[0],
            'player1_id': result[1],
            'player2_id': result[2],
            'start_time': result[3],
            'status': result[4]
        }
    return None

def calculate_fight_winner(player_power, enemy_power, luck):
    """حساب الفائز مع عامل الحظ"""
    # إضافة عامل الحظ للاعب
    final_power = player_power + luck
    
    if final_power > enemy_power:
        return 'player'
    elif enemy_power > final_power:
        return 'enemy'
    else:
        # تعادل - حظ خالص
        return 'player' if random.random() > 0.5 else 'enemy'

def end_fight(fight_id, winner_id, loser_id, is_online=True):
    """إنهاء المباراة وتحديث النقاط"""
    # تحديث حالة المباراة
    cursor.execute('UPDATE active_fights SET status = ? WHERE fight_id = ?', ('finished', fight_id))
    
    if is_online:
        # قتال أونلاين
        cursor.execute('UPDATE players SET elo = elo + 25 WHERE user_id = ?', (winner_id,))
        cursor.execute('UPDATE players SET elo = elo - 25 WHERE user_id = ?', (loser_id,))
        
        # الفائز ياخذ XP وعملات (أقل من قبل)
        winner = get_player(winner_id)
        xp_gain = random.randint(40, 80) + (winner['level'] * 3)
        coin_gain = random.randint(20, 50) + (winner['level'] * 2)
        add_win(winner_id, xp_gain, coin_gain, is_online=True)
        
        # الخاسر يخسر نقاط هجوم ودفاع أقل
        loser = get_player(loser_id)
        new_attack = max(5, loser['attack'] - random.randint(1, 3))
        new_defense = max(5, loser['defense'] - random.randint(1, 3))
        cursor.execute('UPDATE players SET attack = ?, defense = ? WHERE user_id = ?',
                       (new_attack, new_defense, loser_id))
        
        add_loss(loser_id, random.randint(5, 15))
    else:
        # قتال ضد الكمبيوتر - مكافآت أقل
        winner = get_player(winner_id)
        xp_gain = random.randint(10, 30) + (winner['level'] * 1)
        coin_gain = random.randint(5, 15) + (winner['level'] * 1)
        add_win(winner_id, xp_gain, coin_gain, is_online=False)
        
        # الخاسر يخسر نقاط قليلة
        loser = get_player(loser_id)
        new_attack = max(5, loser['attack'] - random.randint(1, 2))
        new_defense = max(5, loser['defense'] - random.randint(1, 2))
        cursor.execute('UPDATE players SET attack = ?, defense = ? WHERE user_id = ?',
                       (new_attack, new_defense, loser_id))
        
        add_loss(loser_id, random.randint(3, 10))
    
    conn.commit()

# ========== دوال الصور ==========
def get_weapon_image(weapon_name):
    cursor.execute('SELECT image FROM weapons WHERE name = ?', (weapon_name,))
    result = cursor.fetchone()
    return result[0] if result else 'weapon_default.png'

def get_armor_image(armor_name):
    cursor.execute('SELECT image FROM armor WHERE name = ?', (armor_name,))
    result = cursor.fetchone()
    return result[0] if result else 'armor_default.png'

print("✅ قاعدة البيانات جاهزة!")
