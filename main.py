import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
import yt_dlp

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_API_KEY")
if not BOT_TOKEN:
    raise ValueError("❌ Переменная окружения TELEGRAM_API_KEY не установлена!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()


# ==================== КЛАВИАТУРА ====================

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Простая клавиатура с кнопками"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="ℹ️ Помощь"),
                KeyboardButton(text="📱 Платформы"),
            ],
            [
                KeyboardButton(text="🔗 Отправить ссылку"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Вставь ссылку на видео или выбери действие 👇"
    )


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def is_supported_url(url: str) -> tuple[bool, str]:
    """Проверяет, поддерживается ли домен ссылки."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    
    supported = [
        "youtube.com", "youtu.be", "twitter.com", "x.com",
        "instagram.com", "tiktok.com", "vk.com", "rutube.ru", "dzen.ru"
    ]
    
    if not netloc:
        return False, "Неверный формат URL"
    
    for domain in supported:
        if domain in netloc:
            return True, ""
    
    return False, f"Домен '{netloc}' не поддерживается"


def download_video(url: str) -> tuple[str, str]:
    """Скачивает видео. Возвращает (путь_к_файлу, название)."""
    temp_dir = tempfile.mkdtemp(prefix="tg_video_download_")
    logger.info(f"Временная директория: {temp_dir}")
    
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(Path(temp_dir) / "video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "twitter": {"api": ["graphql"]},
            "youtube": {"player_client": ["android"]},
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            title = info.get("title", "video")[:50]
            return filepath, title
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise Exception(f"Не удалось скачать видео: {str(e)}")


# ==================== ОБРАБОТЧИКИ ====================

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я скачиваю видео из соцсетей.\n\n"
        "📌 Просто отправь мне ссылку на видео с YouTube, X/Twitter и других платформ.\n"
        "Или используй кнопки ниже для навигации.",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "ℹ️ Помощь")
async def btn_help(message: Message):
    await message.answer(
        "ℹ️ *Как пользоваться:*\n"
        "1. Отправь ссылку на видео (например, с YouTube или X)\n"
        "2. Подожди 10–60 секунд\n"
        "3. Получи видео в чат!\n\n"
        "⚠️ Ограничения:\n"
        "• Макс. размер: 50 МБ (лимит Telegram)\n"
        "• Только публичные видео",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "📱 Платформы")
async def btn_platforms(message: Message):
    await message.answer(
        "📱 *Поддерживаемые платформы:*\n"
        "• 📺 YouTube\n"
        "• 🐦 X / Twitter\n"
        "• 📸 Instagram\n"
        "• 🎵 TikTok\n"
        "• 🆙 VK\n"
        "• ▶️ Rutube\n"
        "• 📰 Дзен",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "🔗 Отправить ссылку")
async def btn_send_link(message: Message):
    await message.answer(
        "📎 Вставь ссылку на видео ниже 👇\n"
        "Примеры:\n"
        "`https://youtube.com/watch?v=abc123`\n"
        "`https://twitter.com/user/status/1234567890`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard()
    )


@router.message(F.text)
async def handle_url(message: Message):
    url = message.text.strip()
    
    # Игнорируем нажатия на кнопки меню (уже обработаны выше)
    if url in ["ℹ️ Помощь", "📱 Платформы", "🔗 Отправить ссылку"]:
        return
    
    # Валидация ссылки
    is_supported, error = is_supported_url(url)
    if not is_supported:
        await message.answer(
            f"❌ {error}\n\n"
            "Поддерживаются: YouTube, X/Twitter, Instagram, TikTok, VK, Rutube, Дзен.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Подтверждение
    msg = await message.answer("📥 Скачиваю видео... ⏳")
    
    try:
        # Скачиваем в отдельном потоке
        filepath, title = await asyncio.to_thread(download_video, url)
        logger.info(f"Видео скачано: {filepath}")
        
        # Проверка размера
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        if file_size > 50:
            await msg.edit_text(
                f"⚠️ Видео слишком большое ({file_size:.1f} МБ).\n"
                "Лимит Telegram: 50 МБ.",
                reply_markup=get_main_keyboard()
            )
            os.remove(filepath)
            os.rmdir(os.path.dirname(filepath))
            return
        
        # Отправка
        await msg.edit_text("📤 Отправляю...")
        video_file = FSInputFile(filepath, filename=f"{title}.mp4")
        await message.answer_video(
            video=video_file,
            supports_streaming=True
        )
        
        # Очистка
        os.remove(filepath)
        os.rmdir(os.path.dirname(filepath))
        await msg.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке {url}: {e}", exc_info=True)
        await msg.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_keyboard()
        )


dp.include_router(router)


async def main():
    logger.info("🚀 Запуск бота...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())