import json
import asyncio
import time
import base64
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from github import Github, GithubException
from dotenv import load_dotenv

load_dotenv()

TOKEN = "7783636058:AAE023bMC_cJZxxLmn-5kMJ883OK7cc7o-E"
GITHUB_TOKEN = "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"
REPO_NAME = "Joxa2047/dador"
FILE_PATH = "all.json"
SUPERADMIN_ID = 7888620964
DEFAULT_CHANNEL = "Probe1u"


bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class GitHubManager:
    def __init__(self):
        try:
            self.g = Github(GITHUB_TOKEN, per_page=100)
            self.repo = self.g.get_repo(REPO_NAME)
            self.initialized = True
            print("GitHubga muvaffaqiyatli ulandi")
        except Exception as e:
            print(f"GitHubga ulanishda xato: {e}")
            self.initialized = False
        self.cache = None
        self.cache_time = 0
        self.cache_expiry = 300  # 5 daqiqa

    def get_default_data(self):
        return {
            "kinolar": {},
            "adminlar": {},
            "foydalanuvchilar": [],
            "kanallar": [DEFAULT_CHANNEL]
        }

    async def check_rate_limit(self):
        try:
            rate_limit = self.g.get_rate_limit().core
            if rate_limit.remaining < 10:
                wait_time = (rate_limit.reset - datetime.now()).total_seconds() + 10
                print(f"GitHub limiti tugab qolmoqda. Qolgan: {rate_limit.remaining}. {wait_time} soniya kutamiz...")
                time.sleep(wait_time)
                return False
            return True
        except Exception as e:
            print(f"Limitni tekshirishda xato: {e}")
            return False

    async def get_data(self):
        # Cache tekshirish
        if self.cache and time.time() - self.cache_time < self.cache_expiry:
            return self.cache

        for attempt in range(3):
            try:
                if not await self.check_rate_limit():
                    continue

                contents = self.repo.get_contents(FILE_PATH, ref="main")
                decoded = base64.b64decode(contents.content).decode('utf-8')
                # JSON faylni to'g'ri parse qilish uchun tekshirish
                try:
                    data = json.loads(decoded)
                except json.JSONDecodeError as e:
                    print(f"JSON parse xatosi: {e}")
                    # Xatolikni tuzatish uchun default ma'lumot qaytarish
                    return self.get_default_data()

                # Cache yangilash
                self.cache = data
                self.cache_time = time.time()
                return data

            except GithubException as e:
                if e.status == 403 and "rate limit" in str(e):
                    reset_time = self.g.get_rate_limit().core.reset
                    wait_time = (reset_time - datetime.now()).total_seconds() + 10
                    print(f"GitHub limiti tugadi. {wait_time} soniya kutamiz...")
                    time.sleep(wait_time)
                    continue
                print(f"GitHub xatosi: {e}")
                return self.get_default_data()
            except Exception as e:
                print(f"Ma'lumotlarni olishda xato: {e}")
                return self.get_default_data()

        return self.get_default_data()

    async def save_data(self, data):
        for attempt in range(3):
            try:
                if not await self.check_rate_limit():
                    continue

                try:
                    contents = self.repo.get_contents(FILE_PATH, ref="main")
                    self.repo.update_file(
                        path=FILE_PATH,
                        message="Bot orqali yangilandi",
                        content=json.dumps(data, indent=4, ensure_ascii=False),
                        sha=contents.sha,
                        branch="main"
                    )
                except:
                    self.repo.create_file(
                        path=FILE_PATH,
                        message="Yangi fayl yaratildi",
                        content=json.dumps(data, indent=4, ensure_ascii=False),
                        branch="main"
                    )

                # Cache yangilash
                self.cache = data
                self.cache_time = time.time()
                return True

            except GithubException as e:
                if e.status == 403 and "rate limit" in str(e):
                    reset_time = self.g.get_rate_limit().core.reset
                    wait_time = (reset_time - datetime.now()).total_seconds() + 10
                    print(f"GitHub limiti tugadi. {wait_time} soniya kutamiz...")
                    time.sleep(wait_time)
                    continue
                print(f"GitHub xatosi: {e}")
                return False
            except Exception as e:
                print(f"Ma'lumotlarni saqlashda xato: {e}")
                return False

        return False


github_manager = GitHubManager()


def buyruqlar_tugmalari():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="cmd_add")],
        [InlineKeyboardButton(text="❌ Kino o'chirish", callback_data="cmd_delete")],
        [InlineKeyboardButton(text="📣 Reklama yuborish", callback_data="cmd_reklama")],
        [InlineKeyboardButton(text="🎥 Kinolar ro'yxati", callback_data="cmd_kinolar")],
        [InlineKeyboardButton(text="🧑‍💻 Adminlar ro'yxati", callback_data="cmd_adminlar")],
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="cmd_addadmin")],
        [InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="cmd_deladmin")],
        [InlineKeyboardButton(text="📢 Kanal qo'shish", callback_data="cmd_addchannel")],
        [InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="cmd_delchannel")],
    ])


def obuna_tugmalari(kanallar):
    tugmalar = []
    for kanal in kanallar:
        tugmalar.append([InlineKeyboardButton(
            text=f"✅ @{kanal} kanaliga obuna bo'lish",
            url=f"https://t.me/{kanal}"
        )])
    tugmalar.append([InlineKeyboardButton(
        text="✅ Obuna bo'ldim",
        callback_data="tekshirish_obuna"
    )])
    return InlineKeyboardMarkup(inline_keyboard=tugmalar)


class KinoQoshish(StatesGroup):
    kod_kutish = State()
    izoh_kutish = State()
    video_kutish = State()


class KanalQoshish(StatesGroup):
    kanal_kutish = State()


class KanalOchirish(StatesGroup):
    kanal_kutish = State()


async def tekshir_obuna(user_id, kanallar):
    natijalar = {}
    for kanal in kanallar:
        try:
            azo = await bot.get_chat_member(chat_id=f"@{kanal}", user_id=user_id)
            natijalar[kanal] = azo.status in ['member', 'administrator', 'creator']
        except Exception as e:
            print(f"@{kanal} kanaliga obunani tekshirishda xato: {e}")
            natijalar[kanal] = False
    return all(natijalar.values()), natijalar


@dp.message(Command("start"))
async def start_handler(message: Message):
    malumot = await github_manager.get_data()
    user_id = str(message.from_user.id)

    # Obunani tekshirish
    obuna, holat = await tekshir_obuna(message.from_user.id, malumot["kanallar"])
    if not obuna:
        obuna_bo_lish_kerak = [kanal for kanal, hol in holat.items() if not hol]
        try:
            await message.reply(
                "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                reply_markup=obuna_tugmalari(obuna_bo_lish_kerak)
            )
        except Exception as e:
            print(f"Obuna xabarini yuborishda xato: {e}")
        return

    # Foydalanuvchini qo'shamiz agar yo'q bo'lsa
    if user_id not in malumot["foydalanuvchilar"]:
        malumot["foydalanuvchilar"].append(user_id)
        await github_manager.save_data(malumot)

    username = message.from_user.username or message.from_user.first_name
    await message.reply(f"Salom, @{username}!\n🎬 Iltimos, kino kodini kiriting:")


@dp.callback_query(F.data == "tekshirish_obuna")
async def obuna_tekshirish(callback: CallbackQuery):
    try:
        malumot = await github_manager.get_data()
        obuna, holat = await tekshir_obuna(callback.from_user.id, malumot["kanallar"])

        if obuna:
            # Foydalanuvchini qo'shamiz agar yo'q bo'lsa
            user_id = str(callback.from_user.id)
            if user_id not in malumot["foydalanuvchilar"]:
                malumot["foydalanuvchilar"].append(user_id)
                await github_manager.save_data(malumot)

            try:
                await callback.message.edit_text(
                    "✅ Obuna tasdiqlandi! Botdan foydalanishingiz mumkin.\n\n" +
                    "🎬 Iltimos, kino kodini kiriting:",
                    reply_markup=None
                )
            except Exception as e:
                print(f"Xabarni o'zgartirishda xato: {e}")
                await callback.answer("✅ Obuna tasdiqlandi! Botdan foydalanishingiz mumkin.")
        else:
            obuna_bo_lish_kerak = [kanal for kanal, hol in holat.items() if not hol]
            try:
                await callback.message.edit_text(
                    "⚠️ Hali barcha kanallarga obuna bo'lmagansiz!",
                    reply_markup=obuna_tugmalari(obuna_bo_lish_kerak)
                )
            except Exception as e:
                print(f"Obuna xabarini o'zgartirishda xato: {e}")
                await callback.answer("⚠️ Hali barcha kanallarga obuna bo'lmagansiz!")
    except Exception as e:
        print(f"Obunani tekshirishda xato: {e}")
        await callback.answer("⚠️ Xatolik yuz berdi, iltimos qayta urunib ko'ring")


@dp.message(Command("addchannel"))
async def kanal_qoshish_handler(message: Message, state: FSMContext):
    if message.from_user.id != SUPERADMIN_ID:
        await message.reply("❌ Faqat superadmin kanal qo'sha oladi.")
        return

    await message.reply("📢 Yangi kanal username ni yuboring (masalan: Probe1u):")
    await state.set_state(KanalQoshish.kanal_kutish)


@dp.message(KanalQoshish.kanal_kutish)
async def kanalni_qoshish(message: Message, state: FSMContext):
    kanal = message.text.strip().replace("@", "")
    if not kanal:
        await message.reply("❌ Iltimos, kanal username ni yuboring!")
        return

    malumot = await github_manager.get_data()
    if kanal not in malumot["kanallar"]:
        malumot["kanallar"].append(kanal)
        if await github_manager.save_data(malumot):
            await message.reply(f"✅ Yangi kanal qo'shildi: @{kanal}")
        else:
            await message.reply("❌ Kanal qo'shishda xato yuz berdi")
    else:
        await message.reply(f"⚠️ @{kanal} allaqachon ro'yxatda bor")

    await state.clear()


@dp.message(Command("delchannel"))
async def kanal_ochirish_handler(message: Message, state: FSMContext):
    if message.from_user.id != SUPERADMIN_ID:
        await message.reply("❌ Faqat superadmin kanal o'chira oladi.")
        return

    malumot = await github_manager.get_data()
    if len(malumot["kanallar"]) <= 1:
        await message.reply("❌ Kamida bitta kanal qolishi kerak!")
        return

    await message.reply("📢 O'chiriladigan kanal username ni yuboring (masalan: Probe1u):\n\n" +
                        "Mavjud kanallar:\n" +
                        "\n".join([f"• @{kanal}" for kanal in malumot["kanallar"]]))
    await state.set_state(KanalOchirish.kanal_kutish)


@dp.message(KanalOchirish.kanal_kutish)
async def kanalni_ochirish(message: Message, state: FSMContext):
    kanal = message.text.strip().replace("@", "")
    if not kanal:
        await message.reply("❌ Iltimos, kanal username ni yuboring!")
        return

    malumot = await github_manager.get_data()
    if kanal in malumot["kanallar"]:
        malumot["kanallar"].remove(kanal)
        if await github_manager.save_data(malumot):
            await message.reply(f"✅ Kanal o'chirildi: @{kanal}")
        else:
            await message.reply("❌ Kanal o'chirishda xato yuz berdi")
    else:
        await message.reply(f"⚠️ @{kanal} kanali topilmadi")

    await state.clear()


@dp.message(Command("commands"))
async def buyruqlarni_korsat(message: Message):
    malumot = await github_manager.get_data()
    if str(message.from_user.id) not in malumot["adminlar"] and message.from_user.id != SUPERADMIN_ID:
        return await message.reply("❌ Siz admin emassiz.")

    await message.reply("📋 <b>Mavjud buyruqlar:</b>",
                        reply_markup=buyruqlar_tugmalari(),
                        parse_mode="HTML")


@dp.callback_query(F.data.startswith("cmd_"))
async def buyruq_malumoti(callback: CallbackQuery):
    buyruq_info = {
        "cmd_add": "🎬 <b>/add</b> - Yangi kino qo'shish",
        "cmd_delete": "❌ <b>/delete &lt;kod&gt;</b> - Kinoni o'chirish",
        "cmd_reklama": "📣 <b>/reklama</b> - Reklama yuborish",
        "cmd_kinolar": "🎥 <b>/kinolar</b> - Kinolar ro'yxati",
        "cmd_adminlar": "🧑‍💻 <b>/adminlar</b> - Adminlar ro'yxati",
        "cmd_addadmin": "➕ <b>/addadmin</b> - Admin qo'shish",
        "cmd_deladmin": "➖ <b>/deladmin</b> - Admin o'chirish",
        "cmd_addchannel": "📢 <b>/addchannel</b> - Kanal qo'shish",
        "cmd_delchannel": "🗑 <b>/delchannel</b> - Kanal o'chirish"
    }
    await callback.message.edit_text(buyruq_info.get(callback.data, "❌ Noma'lum buyruq."), parse_mode="HTML")


# ... (oldingi importlar va sozlamalar o'zgarishsiz qoladi)

class ReklamaYuborish(StatesGroup):
    reklama_kutish = State()


# ... (oldingi class va funksiyalar o'zgarishsiz qoladi)

@dp.message(Command("reklama"))
async def send_advertisement(message: types.Message):
    # Check admin permissions
    malumot = await github_manager.get_data()
    if str(message.from_user.id) not in malumot["adminlar"] and message.from_user.id != SUPERADMIN_ID:
        return await message.reply("Sizda reklama yuborish huquqi yo'q.")

    # Check if message is a reply
    if not message.reply_to_message:
        return await message.reply(
            "Iltimos, reklama uchun kontentni (rasm, video, audio, fayl) *reply* qilib yuboring!\n\n"
            "Masalan:\n1. Avval kontent + izoh yuboring\n2. Keyin shu xabarga /reklama deb reply qiling"
        )

    replied_message = message.reply_to_message
    caption = replied_message.caption or ""
    users = malumot["foydalanuvchilar"]
    success = 0
    failures = 0

    # Determine content type and prepare appropriate sending method
    content_type = None
    send_method = None
    content = None

    if replied_message.photo:
        content_type = "photo"
        content = replied_message.photo[-1].file_id
        send_method = bot.send_photo
    elif replied_message.video:
        content_type = "video"
        content = replied_message.video.file_id
        send_method = bot.send_video
    elif replied_message.voice:
        content_type = "voice"
        content = replied_message.voice.file_id
        send_method = bot.send_voice
    elif replied_message.video_note:
        content_type = "video_note"
        content = replied_message.video_note.file_id
        send_method = bot.send_video_note
    elif replied_message.document:
        content_type = "document"
        content = replied_message.document.file_id
        send_method = bot.send_document
    elif replied_message.audio:
        content_type = "audio"
        content = replied_message.audio.file_id
        send_method = bot.send_audio
    elif replied_message.text:
        content_type = "text"
        content = replied_message.text
        send_method = bot.send_message
    else:
        return await message.reply(
            "❌ Qo'llab-quvvatlanmaydigan kontent turi. Iltimos, rasm, video, audio, fayl yoki matn yuboring.")

    # If no caption for media content, ask for one
    if content_type != "text" and not caption:
        await message.reply(
            "⚠️ Siz kontent tagiga izoh qo'shmagansiz. Izoh qo'shish uchun /caption <izoh> buyrug'ini yuboring.")
        return

    # Send to all users
    for user_id in users:
        try:
            if content_type == "text":
                await send_method(chat_id=user_id, text=content)
            else:
                await send_method(chat_id=user_id, **{content_type: content}, caption=caption)
            success += 1
        except Exception as e:
            print(f"Foydalanuvchiga {user_id} reklama yuborishda xato: {e}")
            failures += 1
            if "bot was blocked by the user" in str(e).lower():
                malumot["foydalanuvchilar"].remove(user_id)
                await github_manager.save_data(malumot)

    # Prepare result message
    result_message = (
        f"📊 Reklama natijasi:\n"
        f"✅ Muvaffaqiyatli yuborildi: {success} ta\n"
        f"❌ Yuborilmadi: {failures} ta\n"
        f"📢 Jami foydalanuvchilar: {len(users)} ta\n"
    )

    if content_type != "text":
        result_message += f"\n📝 Izoh: {caption if caption else 'Yoʻq'}"
        result_message += f"\n📦 Kontent turi: {content_type}"
    else:
        result_message += f"\n📝 Matn: {content[:100]}..." if len(content) > 100 else f"\n📝 Matn: {content}"

    await message.reply(result_message)

@dp.message(Command("kinolar"))
async def list_movies(message: Message):
    malumot = await github_manager.get_data()
    if str(message.from_user.id) not in malumot["adminlar"] and message.from_user.id != SUPERADMIN_ID:
        return await message.reply("Faqat adminlar ko'ra oladi.")

    movies = malumot["kinolar"]
    if not movies:
        return await message.reply("🎥 Hozircha hech qanday kino mavjud emas.")

    text = "🎬 Kino kodlari ro'yxati:\n\n"
    for code, movie in movies.items():
        text += f"📼 Kod: `{code}` - {movie.get('description', 'Izohsiz')}\n"
    await message.reply(text)


@dp.message(Command("adminlar"))
async def list_admins(message: Message):
    if message.from_user.id != SUPERADMIN_ID:
        return await message.reply("Faqat superadmin ko'ra oladi.")

    malumot = await github_manager.get_data()
    admins = malumot["adminlar"]
    if not admins:
        return await message.reply("Adminlar yo'q.")

    text = "👤 Adminlar ro'yxati:\n\n"
    for user_id, admin_name in admins.items():
        text += f"{admin_name} (ID: {user_id})\n"
    await message.reply(text)


@dp.message(Command("addadmin"))
async def add_admin(message: Message):
    if message.from_user.id != SUPERADMIN_ID:
        return await message.reply("Faqat superadmin admin qo'sha oladi.")

    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit():
        return await message.reply("Foydalanish: /addadmin <user_id> <admin_ismi>")

    user_id = parts[1]
    name = parts[2]
    malumot = await github_manager.get_data()

    if user_id in malumot["adminlar"]:
        return await message.reply(f"Bu foydalanuvchi `{name}` allaqachon admin.")

    malumot["adminlar"][user_id] = name
    if await github_manager.save_data(malumot):
        await message.reply(f"✅ Yangi admin qo'shildi: {name} (`{user_id}`)")
    else:
        await message.reply("❌ Admin qo'shishda xato yuz berdi")


@dp.message(Command("deladmin"))
async def del_admin(message: Message):
    if message.from_user.id != SUPERADMIN_ID:
        return await message.reply("Faqat superadmin admin o'chira oladi.")

    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        return await message.reply("Foydalanish: /deladmin <admin_ismi>")

    admin_name = parts[1].strip()
    malumot = await github_manager.get_data()
    admins = malumot["adminlar"]

    admin_id_to_remove = None
    for user_id, name in admins.items():
        if name.lower() == admin_name.lower():
            admin_id_to_remove = user_id
            break

    if admin_id_to_remove:
        del admins[admin_id_to_remove]
        if await github_manager.save_data(malumot):
            await message.reply(f"❌ Admin o'chirildi: {admin_name}")
        else:
            await message.reply("❌ Admin o'chirishda xato yuz berdi")
    else:
        await message.reply("Bu ismga ega admin topilmadi.")


@dp.message(Command("delete"))
async def delete_movie(message: Message):
    malumot = await github_manager.get_data()
    if str(message.from_user.id) not in malumot["adminlar"] and message.from_user.id != SUPERADMIN_ID:
        return await message.reply("Siz admin emassiz.")

    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        return await message.reply("Foydalanish: /delete <kod>")

    code = parts[1].strip()
    movies = malumot["kinolar"]

    if code in movies:
        del movies[code]
        if await github_manager.save_data(malumot):
            await message.reply(f"Kod bo'yicha kino o'chirildi: {code}")
        else:
            await message.reply("❌ Kino o'chirishda xato yuz berdi")
    else:
        await message.reply("Bunday kod topilmadi.")


class AddMovie(StatesGroup):
    waiting_for_code = State()
    waiting_for_description = State()
    waiting_for_video = State()


@dp.message(Command("add"))
async def start_add_movie(message: Message, state: FSMContext):
    malumot = await github_manager.get_data()
    if str(message.from_user.id) not in malumot["adminlar"] and message.from_user.id != SUPERADMIN_ID:
        return await message.reply("Siz admin emassiz.")

    await message.reply("1️⃣ Avval kino uchun <b>kod</b>ni yuboring:", parse_mode="HTML")
    await state.set_state(AddMovie.waiting_for_code)


@dp.message(AddMovie.waiting_for_code, F.text)
async def get_code(message: Message, state: FSMContext):
    code = message.text.strip()
    malumot = await github_manager.get_data()
    movies = malumot["kinolar"]

    if code in movies:
        await message.reply("Bu kod allaqachon mavjud. Boshqa kod kiriting:")
        return

    await state.update_data(code=code)
    await message.reply("2️⃣ Endi kino uchun <b>izoh</b> yuboring:", parse_mode="HTML")
    await state.set_state(AddMovie.waiting_for_description)


@dp.message(AddMovie.waiting_for_description, F.text)
async def get_description(message: Message, state: FSMContext):
    description = message.text.strip()
    await state.update_data(description=description)
    await message.reply("3️⃣ Endi kino <b>video</b>sini yuboring:", parse_mode="HTML")
    await state.set_state(AddMovie.waiting_for_video)


@dp.message(AddMovie.waiting_for_video, F.video)
async def save_video_with_all_data(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("code")
    description = data.get("description")
    video_id = message.video.file_id

    malumot = await github_manager.get_data()
    malumot["kinolar"][code] = {
        "video_id": video_id,
        "description": description
    }

    if await github_manager.save_data(malumot):
        await message.reply(f"✅ Kino saqlandi:\n🎬 Kod: {code}\n📝 Izoh: {description}")
    else:
        await message.reply("❌ Kino saqlashda xato yuz berdi")

    await state.clear()


# ... (qolgan kodlar o'zgarishsiz qoladi)
@dp.message(F.text)
async def kino_yubor(message: Message):
    # Avval obunani tekshirish
    malumot = await github_manager.get_data()
    obuna, holat = await tekshir_obuna(message.from_user.id, malumot["kanallar"])
    if not obuna:
        obuna_bo_lish_kerak = [kanal for kanal, hol in holat.items() if not hol]
        await message.reply(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=obuna_tugmalari(obuna_bo_lish_kerak)
        )
        return

    # Kino kodini qidirish
    kod = message.text.strip()
    if kod in malumot["kinolar"]:
        kino = malumot["kinolar"][kod]
        await message.reply_video(
            video=kino["video_id"],
            caption=f"🎬 {kod}\n📝 {kino.get('description', '')}"
        )
    else:
        await message.reply("❌ Bunday kodli kino topilmadi.")


async def main():
    if not github_manager.initialized:
        print("⚠️ Diqqat: GitHubga ulanmadi, faqat lokal ma'lumotlar ishlatiladi")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
