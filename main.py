import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ⚠️ SOZLAMALAR
BOT_TOKEN = "8210954940:AAHpi__uclI7aNgGaIYj4scS45UwZecnkwI"
CHANNEL_ID = -1003976596089
ADMIN_ID = 8429176166
CARD_NUMBER = "4916 9903 6410 0641"
CARD_HOLDER = "Dosimov Rustam"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class PaymentState(StatesGroup):
    waiting_for_receipt = State()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            subscription_status INTEGER DEFAULT 0,
            expire_date TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, first_name, username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, first_name, username)
        VALUES (?, ?, ?)
    """, (user_id, first_name, username))
    conn.commit()
    conn.close()

def update_subscription(user_id, days):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    expire_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    cursor.execute("""
        UPDATE users 
        SET subscription_status = 1, expire_date = ? 
        WHERE user_id = ?
    """, (expire_date, user_id))
    conn.commit()
    conn.close()
    return expire_date

def deactivate_subscription(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET subscription_status = 0, expire_date = NULL 
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

# --- AVTOMATIK TEKSHIRISH TIZIMI (BACKGROUND TASK) ---
async def check_expired_subscriptions():
    """Har 1 soatda obunasi tugaganlarni aniqlaydi va kanaldan chiqaradi"""
    while True:
        try:
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Obunasi faol va muddati o'tgan foydalanuvchilarni olish
            cursor.execute("""
                SELECT user_id FROM users 
                WHERE subscription_status = 1 AND expire_date <= ?
            """, (now_str,))
            expired_users = cursor.fetchall()
            conn.close()

            for user in expired_users:
                user_id = user[0]
                try:
                    # Kanaldan chiqarish (Ban qilib, darhol Unban qilinsa kanaldan chiqadi)
                    await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    
                    deactivate_subscription(user_id)
                    
                    # Foydalanuvchiga ogohlantirish yuborish
                    await bot.send_message(
                        chat_id=user_id,
                        text="⚠️ **Sizning VIP Club obunangiz muddati tugadi.**\n\n"
                             "Kanalga qayta kirish uchun obunani yangilang!",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="⭐ Obunani yangilash", callback_data="tariffs")]]
                        )
                    )
                    print(f"User {user_id} kanaldan chiqarildi (Obuna tugadi).")
                except Exception as e:
                    print(f"User {user_id} ni chiqarishda xatolik: {e}")

        except Exception as ex:
            print(f"Tekshirishda xatolik: {ex}")

        # 1 soat (3600 soniya) kutib keyin qayta tekshiradi
        await asyncio.sleep(3600)

# --- TUGMALAR ---
def get_main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Obuna tariflari", callback_data="tariffs"),
                InlineKeyboardButton(text="ℹ️ Kanal haqida", callback_data="about")
            ],
            [
                InlineKeyboardButton(text="👤 Profilim", callback_data="profile"),
                InlineKeyboardButton(text="📞 Qo'llab-quvvatlash", callback_data="support")
            ]
        ]
    )

def get_tariffs_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 oy — 40,000 so'm", callback_data="select_30")
            ],
            [
                InlineKeyboardButton(text="3 oy — 100,000 so'm (Tejamkor)", callback_data="select_90")
            ],
            [
                InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main")
            ]
        ]
    )

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    add_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username
    )
    await message.answer(
        f"Salom, {message.from_user.first_name}!\n\n"
        "VIP Club rasmiy botiga xush kelibsiz!\n"
        "Yopiq kanalimizga obuna bo'lish uchun pastdagi tugmalardan foydalaning.",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: types.CallbackQuery):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT subscription_status, expire_date FROM users WHERE user_id = ?", (callback.from_user.id,))
    row = cursor.fetchone()
    conn.close()

    status = "Nofaol ❌"
    expire = "Mavjud emas"

    if row and row[0] == 1:
        status = "Faol ✅"
        expire = row[1] if row[1] else "Noma'lum"

    await callback.message.edit_text(
        f"👤 **Sizning profilingiz:**\n\n"
        f"🆔 ID: `{callback.from_user.id}`\n"
        f"📌 Obuna holati: **{status}**\n"
        f"⏳ Tugash muddati: **{expire}**",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main")]]
        ),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "tariffs")
async def tariffs_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💳 **Obuna tarifini tanlang:**\n\n"
        "O'zingizga ma'qul muddatni tanlang va to'lovni amalga oshiring:",
        reply_markup=get_tariffs_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "about")
async def about_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📌 **VIP Kanalimizda nimalar bor?**\n\n"
        "• Eksklyuziv darsliklar va materiallar\n"
        "• Har kungi tahlillar va maslahatlar\n"
        "• Yopiq hamjamiyat va muloqot\n\n"
        "Obuna bo'lish uchun pastdagi tugmani bosing:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⭐ Obuna bo'lish", callback_data="tariffs")],
                [InlineKeyboardButton(text="⬅️️ Orqaga", callback_data="back_to_main")]
            ]
        ),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "back_to_main")
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"Salom, {callback.from_user.first_name}!\n\n"
        "VIP Club rasmiy botiga xush kelibsiz!\n"
        "Yopiq kanalimizga obuna bo'lish uchun pastdagi tugmalardan foydalaning.",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "support")
async def support_handler(callback: types.CallbackQuery):
    await callback.answer("Savollaringiz bo'lsa, adminga murojaat qiling: @rustamvv_11", show_alert=True)

@dp.callback_query(F.data.startswith("select_"))
async def select_tariff(callback: types.CallbackQuery, state: FSMContext):
    days = int(callback.data.split("_")[1])
    amount = "40,000 so'm" if days == 30 else "100,000 so'm"

    await state.update_data(chosen_days=days, amount=amount)
    await state.set_state(PaymentState.waiting_for_receipt)

    await callback.message.edit_text(
        f"💳 **To'lov ma'lumotlari:**\n\n"
        f"📌 Tanlangan tarif: **{days} kun**\n"
        f"💰 To'lov summasi: **{amount}**\n\n"
        f"💳 Karta raqam: `{CARD_NUMBER}`\n"
        f"👤 Karta egasi: **{CARD_HOLDER}**\n\n"
        f"📥 **To'lovni amalga oshirgach, to'lov chekini (rasm/skrinshot) shu yerga yuboring:**",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_main")]]
        ),
        parse_mode="Markdown"
    )

@dp.message(PaymentState.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    days = data.get("chosen_days")
    amount = data.get("amount")
    
    photo_id = message.photo[-1].file_id
    user_info = f"👤 Foydalanuvchi: {message.from_user.full_name}\n" \
                f"🆔 ID: `{message.from_user.id}`\n" \
                f"🏷 Username: @{message.from_user.username}\n" \
                f"⏳ Tarif: **{days} kun ({amount})**"

    admin_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{message.from_user.id}_{days}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{message.from_user.id}")
            ]
        ]
    )

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=f"📩 **Yangi to'lov cheki keldi!**\n\n{user_info}",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )

    await message.answer(
        "✅ **To'lov chekingiz qabul qilindi!**\n\n"
        "Admin to'lovni tekshirib, tez orada obunani faollashtiradi va yopiq kanal havolasini yuboradi.",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@dp.message(PaymentState.waiting_for_receipt)
async def wrong_receipt_format(message: types.Message):
    await message.answer("⚠️ Iltimos, to'lov chekini **rasm (skrinshot)** ko'rinishida yuboring.")

@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: types.CallbackQuery):
    _, user_id, days = callback.data.split("_")
    user_id = int(user_id)
    days = int(days)

    expire_date = update_subscription(user_id, days)

    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )

        await bot.send_message(
            chat_id=user_id,
            text=f"🎉 **To'lovingiz tasdiqlandi!**\n\n"
                 f"Sizning obunangiz **{expire_date}** gacha faollashtirildi.\n\n"
                 f"🔗 Yopiq kanalga kirish uchun maxsus havola:\n{invite_link.invite_link}\n\n"
                 f"⚠️ *Eslatma: Bu havola bir martalik va faqat siz uchun!*",
            parse_mode="Markdown"
        )
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n✅ **ADMIN TAROFIDAN TASDIQLANDI!**",
            reply_markup=None
        )
    except Exception as e:
        await callback.answer(f"Xatolik yuz berdi: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    await bot.send_message(
        chat_id=user_id,
        text="❌ **To'lovingiz rad etildi.**\n\nTo'lov cheki yaroqsiz yoki pul tushmagan bo'lishi mumkin. Qayta urinib ko'ring yoki qo'llab-quvvatlash xizmatiga murojaat qiling."
    )
    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n❌ **ADMIN TAROFIDAN RAD ETILDI.**",
        reply_markup=None
    )

async def main():
    init_db()
    # Obunalarni orqa fonda avtomatik tekshiradigan vazifani ishga tushirish
    asyncio.create_task(check_expired_subscriptions())
    
    print("Bot va avto-tekshiruv muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())