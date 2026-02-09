import telebot
from telebot import types
import requests
import json
import base64
import time
import threading

# --- 🔐 ТВОИ НАСТРОЙКИ (ВШИТЫ) ---
BOT_TOKEN = '8266125587:AAFjQ13rodEhwJW-Gre8nyNVue02xjo4TPg'
GITHUB_TOKEN = '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'
REPO = 'gol131111-ctrl/electrum-'  # Убедись, что название точно такое
DB_FILE = 'db.json'

bot = telebot.TeleBot(BOT_TOKEN)

# --- 🌍 ЯЗЫКИ ---
LANG = {
    'ru': {
        'menu': "💎 ГЛАВНОЕ МЕНЮ",
        'cat': "📦 Каталог",
        'prof': "👤 Профиль",
        'help': "🆘 Поддержка",
        'topup': "💰 Пополнить",
        'empty': "Категория пуста",
        'buy': "💳 КУПИТЬ",
        'desc': "📝 Описание",
        'price': "Цена",
        'back': "🔙 Назад"
    },
    'uk': {
        'menu': "💎 ГОЛОВНЕ МЕНЮ",
        'cat': "📦 Каталог",
        'prof': "👤 Профіль",
        'help': "🆘 Підтримка",
        'topup': "💰 Поповнити",
        'empty': "Категорія порожня",
        'buy': "💳 КУПИТИ",
        'desc': "📝 Опис",
        'price': "Ціна",
        'back': "🔙 Назад"
    }
}

# --- 📡 СВЯЗЬ С GITHUB ---
def get_db():
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{DB_FILE}"
        headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Cache-Control': 'no-cache'}
        res = requests.get(url, headers=headers).json()
        if 'content' not in res: return None, None
        content = base64.b64decode(res['content']).decode('utf-8')
        return json.loads(content), res['sha']
    except Exception as e:
        print(f"Ошибка БД: {e}")
        return None, None

def save_db(data, sha, msg="System Update"):
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{DB_FILE}"
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        content_encoded = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
        payload = {"message": msg, "content": content_encoded, "sha": sha}
        requests.put(url, headers=headers, json=payload)
    except: pass

# --- 🔄 ФОНОВАЯ ЗАДАЧА: РАССЫЛКА ---
def broadcast_watcher():
    while True:
        try:
            db, sha = get_db()
            if db and db.get('broadcast') and db['broadcast'].get('text'):
                bc = db['broadcast']
                txt = bc['text']
                photo = bc.get('photo')
                btn_txt = bc.get('btn_text')
                btn_url = bc.get('btn_url')

                print(f"📢 РАССЫЛКА: {txt[:20]}...")
                
                markup = None
                if btn_txt and btn_url:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(btn_txt, url=btn_url))

                count = 0
                for u in db['users']:
                    try:
                        if photo and len(photo) > 5:
                            bot.send_photo(u['id'], photo, caption=txt, reply_markup=markup, parse_mode='HTML')
                        else:
                            bot.send_message(u['id'], txt, reply_markup=markup, parse_mode='HTML')
                        count += 1
                        time.sleep(0.05) # Анти-спам задержка
                    except: pass
                
                # Очистка задачи
                db['broadcast'] = {"text": "", "photo": "", "btn_text": "", "btn_url": ""}
                save_db(db, sha, "Broadcast Completed")
                print(f"✅ Успешно отправлено: {count}")
        except: pass
        time.sleep(15) # Проверка каждые 15 сек

threading.Thread(target=broadcast_watcher, daemon=True).start()

# --- 🤖 ЛОГИКА БОТА ---
def get_user(uid, db):
    return next((u for u in db.get('users', []) if u['id'] == uid), None)

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    username = message.from_user.username
    db, sha = get_db()
    
    u = get_user(uid, db)
    if not u:
        # Регистрация: Выбор языка
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="reg_ru"),
               types.InlineKeyboardButton("🇺🇦 Українська", callback_data="reg_uk"))
        bot.send_message(uid, "👋 <b>Electrum Store</b>\n\nВыберите язык / Оберіть мову:", reply_markup=kb, parse_mode='HTML')
    else:
        # Обновляем юзернейм если сменился
        if u.get('username') != username:
            u['username'] = username
            save_db(db, sha, "Username update")
        show_menu(uid, u['lang'])

@bot.callback_query_handler(func=lambda c: c.data.startswith('reg_'))
def register(c):
    lang = c.data.split('_')[1]
    uid = c.message.chat.id
    username = c.message.chat.username
    
    db, sha = get_db()
    # Проверка дублей
    if not get_user(uid, db):
        new_user = {
            "id": uid, 
            "username": username, 
            "balance": 0, 
            "lang": lang, 
            "purchase_count": 0
        }
        db['users'].append(new_user)
        save_db(db, sha, f"New User {uid}")
    
    bot.delete_message(uid, c.message.message_id)
    show_menu(uid, lang)

def show_menu(uid, lang_code):
    l = LANG.get(lang_code, LANG['ru'])
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(l['cat'], l['prof'])
    kb.add(l['topup'], l['help'])
    bot.send_message(uid, l['menu'], reply_markup=kb)

@bot.message_handler(content_types=['text'])
def handle_text(m):
    uid = m.chat.id
    db, _ = get_db()
    u = get_user(uid, db)
    if not u: return start(m) # Если юзера нет в базе
    
    l = LANG[u['lang']]

    if m.text == l['cat']:
        # Показываем список КАТЕГОРИЙ
        products = db.get('products', [])
        cats = sorted(list(set(p.get('category', 'Разное') for p in products)))
        
        if not cats:
            bot.send_message(uid, l['empty'])
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(types.InlineKeyboardButton(f"📂 {c}", callback_data=f"cat_{c}"))
        bot.send_message(uid, l['cat'], reply_markup=kb)

    elif m.text == l['prof']:
        # Считаем кешбэк уровень
        cb_lvl = 10 if u.get('purchase_count', 0) == 0 else 5
        txt = (
            f"👤 <b>ID:</b> <code>{uid}</code>\n"
            f"📛 <b>User:</b> @{u.get('username', 'Anon')}\n"
            f"💰 <b>Balance:</b> ${u['balance']}\n"
            f"💎 <b>Cashback Level:</b> {cb_lvl}%"
        )
        bot.send_message(uid, txt, parse_mode='HTML')

    elif m.text == l['help']:
        bot.send_message(uid, "👨‍💻 <b>SUPPORT:</b>\n👉 @Ssupport_electrum", parse_mode='HTML')

    elif m.text == l['topup']:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("👨‍💻 Manager", url="https://t.me/Electrum_Store"))
        bot.send_message(uid, "💳 Для пополнения напишите менеджеру:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('cat_'))
def show_products(c):
    cat = c.data.split('_', 1)[1]
    db, _ = get_db()
    u = get_user(c.message.chat.id, db)
    l = LANG[u['lang']]
    
    # Фильтруем товары по категории
    items = [p for p in db.get('products', []) if p.get('category') == cat]
    
    if not items:
        bot.answer_callback_query(c.id, l['empty'])
        return

    bot.delete_message(c.message.chat.id, c.message.message_id)
    
    for p in items:
        name = p.get(f'name_{u["lang"]}', p['name_ru'])
        desc = p.get(f'desc_{u["lang"]}', p['desc_ru'])
        
        txt = f"<b>{name}</b>\n\n{l['desc']}: {desc}\n\n🏷 {l['price']}: <b>${p['price']}</b>"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(l['buy'], url="https://t.me/Electrum_Store"))
        bot.send_message(c.message.chat.id, txt, parse_mode='HTML', reply_markup=kb)

print("🚀 ELECTRUM SYSTEM STARTED...")
bot.polling(none_stop=True)
