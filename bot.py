import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

from content import (
    QUESTIONS,
    RESTART_BUTTON,
    RESULTS,
    TEXT_FALLBACK,
    WELCOME_BUTTON,
    WELCOME_TEXT,
    get_available_buttons,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не задана. Создайте файл .env")

router = Router()


# ── helpers ──────────────────────────────────────────────────────────────────

def _find_selected_label(question_index: int, history: str, chosen: str) -> str:
    available = get_available_buttons(question_index, history)
    for label, number in available:
        if number == chosen:
            return label
    return chosen


async def _freeze_message(callback: CallbackQuery, question_index: int, history: str, chosen: str) -> None:
    question_text = QUESTIONS[question_index]["text"]
    selected_label = _find_selected_label(question_index, history, chosen)
    frozen_text = f"{question_text}\n\n✅ <b>{selected_label}</b>"
    await callback.message.edit_text(frozen_text, reply_markup=None, parse_mode="HTML")


def _question_keyboard(question_index: int, history: str) -> InlineKeyboardMarkup:
    available = get_available_buttons(question_index, history)
    buttons = []
    for label, number in available:
        if question_index < len(QUESTIONS) - 1:
            cb = f"ans_{history}_{number}" if history else f"ans_{number}"
        else:
            cb = f"res_{history}_{number}" if history else f"res_{number}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=WELCOME_BUTTON, callback_data="start_quiz")]
        ]
    )


def _restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=RESTART_BUTTON, callback_data="start_quiz")]
        ]
    )


# ── handlers ─────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT,
        reply_markup=_welcome_keyboard(),
    )


@router.callback_query(F.data == "start_quiz")
async def on_start_quiz(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        QUESTIONS[0]["text"],
        reply_markup=_question_keyboard(question_index=0, history=""),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ans_"))
async def on_answer(callback: CallbackQuery) -> None:
    history = callback.data[len("ans_"):]
    question_index = history.count("_") + 1
    prev_question_index = question_index - 1
    prev_history = "_".join(history.split("_")[:-1])
    chosen = history.split("_")[-1]

    await _freeze_message(callback, prev_question_index, prev_history, chosen)
    await callback.message.answer(
        QUESTIONS[question_index]["text"],
        reply_markup=_question_keyboard(question_index=question_index, history=history),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("res_"))
async def on_result(callback: CallbackQuery) -> None:
    key = callback.data[len("res_"):]
    result_text = RESULTS.get(key, "Что-то пошло не так 🤔 Попробуй ещё раз!")
    parts = key.split("_")
    prev_history = "_".join(parts[:-1])
    chosen = parts[-1]

    await _freeze_message(callback, 2, prev_history, chosen)
    await callback.message.answer(
        result_text,
        reply_markup=_restart_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message()
async def fallback_text(message: Message) -> None:
    await message.answer(TEXT_FALLBACK)


# ── entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
