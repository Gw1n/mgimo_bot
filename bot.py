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
    SCORING_INDICES,
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
    """Finds the button label the user clicked."""
    available = get_available_buttons(question_index, history)
    for label, number in available:
        if number == chosen:
            return label
    return chosen


async def _freeze_message(callback: CallbackQuery, question_index: int, history: str, chosen: str) -> None:
    """Freezes the old message: shows question + selected answer, removes buttons."""
    question_text = QUESTIONS[question_index]["text"]
    selected_label = _find_selected_label(question_index, history, chosen)
    frozen_text = f"{question_text}\n\n✅ <b>{selected_label}</b>"
    await callback.message.edit_text(frozen_text, reply_markup=None, parse_mode="HTML")


def _question_keyboard(question_index: int, history: str) -> InlineKeyboardMarkup:
    """Builds inline keyboard for a question.

    For scoring questions: callback = ans_{history}_{number} or res_{history}_{number}.
    For filler questions: callback = filler_{qidx}_{history}_{number}.
    """
    available = get_available_buttons(question_index, history)
    is_scoring = QUESTIONS[question_index]["scores"]
    is_last = question_index == len(QUESTIONS) - 1
    is_last_scoring = is_scoring and question_index == SCORING_INDICES[-1]
    buttons = []
    for label, number in available:
        if not is_scoring:
            # Filler: carry history and question index through
            cb = f"filler_{question_index}_{history}_{number}" if history else f"filler_{question_index}__{number}"
        elif is_last_scoring or is_last:
            # Last scoring question → result
            cb = f"res_{history}_{number}" if history else f"res_{number}"
        else:
            # Intermediate scoring question
            cb = f"ans_{history}_{number}" if history else f"ans_{number}"
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
    """Scoring answer → freeze old, advance to next question."""
    # ans_1 or ans_1_2 → history = "1" / "1_2"
    history = callback.data[len("ans_"):]
    answers = history.split("_")
    scoring_count = len(answers)  # how many scoring answers so far
    chosen = answers[-1]
    prev_history = "_".join(answers[:-1])

    # The scoring question that was just answered
    prev_scoring_qi = SCORING_INDICES[scoring_count - 1]

    await _freeze_message(callback, prev_scoring_qi, prev_history, chosen)

    # Next question in the overall list
    next_qi = prev_scoring_qi + 1
    await callback.message.answer(
        QUESTIONS[next_qi]["text"],
        reply_markup=_question_keyboard(question_index=next_qi, history=history),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("filler_"))
async def on_filler(callback: CallbackQuery) -> None:
    """Filler answer → freeze old, advance to next question. History unchanged."""
    # filler_{qidx}_{history}_{chosen} or filler_{qidx}__{chosen} (empty history)
    payload = callback.data[len("filler_"):]
    parts = payload.split("_")
    filler_qi = int(parts[0])
    chosen = parts[-1]
    # history is between qidx and chosen; may be empty
    history = "_".join(parts[1:-1]).strip("_")

    await _freeze_message(callback, filler_qi, history, chosen)

    # Next question in the overall list
    next_qi = filler_qi + 1
    await callback.message.answer(
        QUESTIONS[next_qi]["text"],
        reply_markup=_question_keyboard(question_index=next_qi, history=history),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("res_"))
async def on_result(callback: CallbackQuery) -> None:
    """Final scoring answer → freeze old, show result."""
    key = callback.data[len("res_"):]
    result_text = RESULTS.get(key, "Что-то пошло не так 🤔 Попробуй ещё раз!")
    parts = key.split("_")
    prev_history = "_".join(parts[:-1])
    chosen = parts[-1]

    await _freeze_message(callback, SCORING_INDICES[-1], prev_history, chosen)
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
