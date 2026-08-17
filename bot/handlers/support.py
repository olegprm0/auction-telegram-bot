import asyncio
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.utils.keyboards import get_complaint_keyboard, get_support_keyboard
from config.settings import SUPPORT_IDS
from database.db import SessionLocal
from database.models import Complaint, Lot, LotStatus, SupportQuestion, User, UserRole

router = Router()
logger = logging.getLogger(__name__)


async def check_user_banned(user_id: int, message_or_callback) -> bool:
    """Проверяет, заблокирован ли пользователь"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user and user.is_banned:
            ban_message = (
                "❌ **Доступ запрещен!**\n\n"
                "Ваш аккаунт заблокирован администратором.\n"
                "Обратитесь к администратору для разблокировки."
            )

            if hasattr(message_or_callback, "message"):
                # Это callback query
                await message_or_callback.answer(ban_message, parse_mode="Markdown")
            else:
                # Это message
                await message_or_callback.answer(ban_message, parse_mode="Markdown")

            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке блокировки пользователя: {e}")
        return False
    finally:
        db.close()


class SupportStates(StatesGroup):
    waiting_for_question = State()


def has_support_permissions(user_id: int) -> bool:
    """Право работы с поддержкой: модераторы и супер-админы"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        return bool(user and user.role in {UserRole.MODERATOR, UserRole.SUPER_ADMIN})
    except Exception:
        return False
    finally:
        db.close()


@router.callback_query(F.data == "acknowledge")
async def acknowledge_and_delete(callback: CallbackQuery):
    """Подтверждает прочтение и удаляет сообщение через 1 минуту."""
    try:
        await callback.answer("Удалю через 1 минуту")

        chat_id = callback.message.chat.id if callback.message else None
        message_id = callback.message.message_id if callback.message else None

        # Убираем клавиатуру, чтобы не жали повторно
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        if chat_id and message_id:

            async def _del():
                await asyncio.sleep(60)
                try:
                    from bot.main import bot

                    await bot.delete_message(chat_id, message_id)
                except Exception as e:
                    logger.debug(
                        f"Не удалось удалить сообщение {message_id} в {chat_id}: {e}"
                    )

            asyncio.create_task(_del())
    except Exception as e:
        logger.error(f"Ошибка acknowledge: {e}")


@router.message(Command("support"))
async def support_command(message: Message, state: FSMContext):
    """/support — для пользователей: начать диалог с поддержкой (отвечают модераторы)."""
    try:
        await message.answer(
            "📝 <b>Обращение в поддержку</b>\n\nОпишите ваш вопрос или проблему.",
            parse_mode="HTML",
        )
        await state.set_state(SupportStates.waiting_for_question)
    except Exception as e:
        logger.error(f"Ошибка в /support: {e}")
        await message.answer("❌ Ошибка поддержки. Попробуйте позже")


@router.message(Command("support_panel"))
async def support_panel(message: Message):
    """Панель поддержки для модераторов и супер-админов"""
    if not has_support_permissions(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    await message.answer(
        "🆘 <b>Служба поддержки</b>\n\nВыберите раздел:",
        reply_markup=get_support_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ask_support")
async def ask_support(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс обращения в поддержку"""
    await callback.answer()
    await callback.message.edit_text(
        "📝 **Обращение в поддержку**\n\n"
        "Опишите ваш вопрос или проблему. "
        "Мы постараемся помочь вам в ближайшее время."
    )
    await state.set_state(SupportStates.waiting_for_question)


@router.message(SupportStates.waiting_for_question)
async def process_user_question(message: Message, state: FSMContext):
    """Обрабатывает вопрос пользователя"""
    question_text = message.text.strip()

    if len(question_text) < 10:
        await message.answer(
            "❌ Вопрос должен содержать минимум 10 символов.\n"
            "Пожалуйста, опишите проблему подробнее."
        )
        return

    # Сохраняем вопрос в базу данных
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден.")
            await state.clear()
            return

        support_question = SupportQuestion(
            user_id=user.id,
            question=question_text,
            status="pending",
        )

        db.add(support_question)
        db.commit()

        await message.answer(
            "✅ **Вопрос отправлен в поддержку!**\n\n"
            f"📝 <b>Номер вопроса:</b> #{support_question.id}\n"
            f"📅 <b>Дата отправки:</b> {support_question.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            "Мы ответим вам в ближайшее время.",
            parse_mode="HTML",
        )

        # Уведомляем службу поддержки
        await notify_support_about_question(support_question, user)

    except Exception as e:
        logger.error(f"Ошибка при создании вопроса: {e}")
        await message.answer("❌ Ошибка при отправке вопроса. Попробуйте позже.")
    finally:
        db.close()
        await state.clear()


async def notify_support_about_question(question: SupportQuestion, user: User):
    """Уведомляет службу поддержки о новом вопросе"""
    try:
        from bot.main import bot  # Импортируем бота

        support_message = f"""
❓ <b>НОВЫЙ ВОПРОС В ПОДДЕРЖКУ</b>

📝 <b>Вопрос #{question.id}</b>
👤 <b>От:</b> {user.first_name} (@{user.username or 'N/A'})
📅 <b>Дата:</b> {question.created_at.strftime('%d.%m.%Y %H:%M')}

📝 <b>Вопрос:</b>
{question.question}

🔗 <b>Действия:</b>
• /answer_question_{question.id} - Ответить на вопрос
        """.strip()

        # Отправляем уведомление модераторам и супер-админам (с кнопкой подтверждения)
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        ack_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Прочитал", callback_data="acknowledge")]
            ]
        )

        # Собираем получателей из БД; если не найдены — используем SUPPORT_IDS
        db = SessionLocal()
        try:
            moderators = (
                db.query(User)
                .filter(User.role.in_([UserRole.MODERATOR, UserRole.SUPER_ADMIN]))
                .all()
            )
            recipient_ids = {u.telegram_id for u in moderators if u.telegram_id}
        finally:
            db.close()

        if not recipient_ids:
            recipient_ids = set(SUPPORT_IDS)

        for support_id in recipient_ids:
            try:
                await bot.send_message(
                    chat_id=support_id,
                    text=support_message,
                    parse_mode="HTML",
                    reply_markup=ack_keyboard,
                )
            except Exception as e:
                logger.error(
                    f"Ошибка при отправке уведомления поддержке {support_id}: {e}"
                )

    except Exception as e:
        logger.error(f"Ошибка при уведомлении поддержки: {e}")


# Команда /admin_support удалена по требованию. Доступ к панели поддержки оставлен через кнопки/меню.


@router.callback_query(F.data == "pending_lots")
async def show_pending_lots(callback: CallbackQuery):
    """Показывает лоты на модерации"""
    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    db = SessionLocal()
    try:
        pending_lots = db.query(Lot).filter(Lot.status == LotStatus.PENDING).all()

        if not pending_lots:
            await callback.message.edit_text("📋 Нет лотов на модерации")
            return

        text = "📋 **Лоты на модерации:**\n\n"
        for lot in pending_lots:
            seller = db.query(User).filter(User.id == lot.seller_id).first()
            text += f"🔸 **{lot.title}**\n"
            text += f"💰 Цена: {lot.starting_price:,.2f} ₽\n"
            text += f"👤 Продавец: {seller.first_name}\n"
            text += f"📅 Создан: {lot.created_at.strftime('%d.%m.%Y')}\n\n"

        await callback.message.edit_text(text)

    except Exception as e:
        logger.error(f"Ошибка при получении лотов на модерации: {e}")
        await callback.answer("Ошибка при получении данных")
    finally:
        db.close()


@router.callback_query(F.data == "pending_complaints")
async def show_pending_complaints(callback: CallbackQuery):
    """Показывает жалобы на рассмотрении"""
    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    db = SessionLocal()
    try:
        pending_complaints = (
            db.query(Complaint).filter(Complaint.status == "pending").all()
        )

        if not pending_complaints:
            await callback.message.edit_text("📋 Нет жалоб на рассмотрении")
            return

        text = "📋 **Жалобы на рассмотрении:**\n\n"
        for complaint in pending_complaints:
            complainant = (
                db.query(User).filter(User.id == complaint.complainant_id).first()
            )
            target = db.query(User).filter(User.id == complaint.target_user_id).first()

            text += f"🔸 **Жалоба #{complaint.id}**\n"
            text += f"👤 От: {complainant.first_name}\n"
            text += f"🎯 На: {target.first_name}\n"
            text += f"📅 Дата: {complaint.created_at.strftime('%d.%m.%Y')}\n\n"

        await callback.message.edit_text(text)

    except Exception as e:
        logger.error(f"Ошибка при получении жалоб: {e}")
        await callback.answer("Ошибка при получении данных")
    finally:
        db.close()


@router.callback_query(F.data == "approve_lot")
async def approve_lot_handler(callback: CallbackQuery):
    """Обрабатывает одобрение лота"""
    await callback.answer("Функция одобрения лотов будет добавлена позже")


@router.callback_query(F.data == "reject_lot")
async def reject_lot_handler(callback: CallbackQuery):
    """Обрабатывает отклонение лота"""
    await callback.answer("Функция отклонения лотов будет добавлена позже")


@router.callback_query(F.data == "review_complaint")
async def review_complaint_handler(callback: CallbackQuery):
    """Показывает жалобы для рассмотрения"""
    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    db = SessionLocal()
    try:
        pending_complaints = (
            db.query(Complaint).filter(Complaint.status == "pending").all()
        )

        if not pending_complaints:
            await callback.message.edit_text(
                "📋 **Жалобы на рассмотрении**\n\n" "Нет жалоб для рассмотрения."
            )
            return

        text = "📋 **Жалобы на рассмотрении:**\n\n"
        for complaint in pending_complaints[:10]:  # Показываем первые 10
            complainant = (
                db.query(User).filter(User.id == complaint.complainant_id).first()
            )
            target_user = (
                db.query(User).filter(User.id == complaint.target_user_id).first()
            )

            complainant_name = complainant.first_name if complainant else "Неизвестно"
            target_name = target_user.first_name if target_user else "Неизвестно"

            text += f"🔸 **Жалоба #{complaint.id}**\n"
            text += f"👤 От: {complainant_name}\n"
            text += f"🎯 На: {target_name}\n"
            text += f"📅 {complaint.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"📝 {complaint.reason[:50]}{'...' if len(complaint.reason) > 50 else ''}\n\n"

        if len(pending_complaints) > 10:
            text += f"... и еще {len(pending_complaints) - 10} жалоб"

        # Добавляем кнопки для навигации
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_support")]
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при получении жалоб: {e}")
        await callback.answer("Ошибка при получении данных")
    finally:
        db.close()


@router.callback_query(F.data.startswith("review_complaint_detail:"))
async def review_complaint_detail(callback: CallbackQuery):
    """Показывает детали жалобы для рассмотрения"""
    await callback.answer()

    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    complaint_id = int(callback.data.split(":")[1])

    db = SessionLocal()
    try:
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            await callback.message.edit_text("❌ Жалоба не найдена")
            return

        complainant = db.query(User).filter(User.id == complaint.complainant_id).first()
        target_user = db.query(User).filter(User.id == complaint.target_user_id).first()

        complainant_name = complainant.first_name if complainant else "Неизвестно"
        target_name = target_user.first_name if target_user else "Неизвестно"

        text = f"""
📝 **ЖАЛОБА #{complaint.id}**

👤 **От:** {complainant_name} (@{complainant.username or 'N/A'})
🎯 **На:** {target_name} (@{target_user.username or 'N/A'})
📅 **Дата:** {complaint.created_at.strftime('%d.%m.%Y %H:%M')}
📊 **Статус:** {complaint.status}

📝 **Причина:**
{complaint.reason}

{('📎 **Доказательства:**' + chr(10) + str(complaint.evidence)) if complaint.evidence else ''}

{('✅ **Решение:**' + chr(10) + str(complaint.resolution)) if complaint.resolution else ''}
        """.strip()

        # Кнопки для действий с жалобой
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Разрешить",
                        callback_data=f"resolve_complaint:{complaint_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"reject_complaint:{complaint_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="⚠️ Выдать страйк",
                        callback_data=f"strike_user:{complaint.target_user_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад к жалобам", callback_data="review_complaint"
                    ),
                ],
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при получении деталей жалобы: {e}")
        await callback.answer("Ошибка при получении данных")
    finally:
        db.close()


@router.callback_query(F.data.startswith("resolve_complaint:"))
async def resolve_complaint_handler(callback: CallbackQuery):
    """Разрешает жалобу"""
    await callback.answer()

    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    complaint_id = int(callback.data.split(":")[1])

    db = SessionLocal()
    try:
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            await callback.message.edit_text("❌ Жалоба не найдена")
            return

        # Обновляем статус жалобы
        complaint.status = "resolved"
        complaint.is_resolved = True
        complaint.resolution = "Жалоба разрешена службой поддержки"
        complaint.reviewed_by = callback.from_user.id
        complaint.reviewed_at = datetime.now()

        db.commit()

        await callback.message.edit_text(
            f"✅ **Жалоба #{complaint_id} разрешена**\n\n"
            "Жалоба была успешно разрешена и закрыта.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Ошибка при разрешении жалобы: {e}")
        await callback.answer("Ошибка при разрешении жалобы")
    finally:
        db.close()


@router.callback_query(F.data.startswith("reject_complaint:"))
async def reject_complaint_handler(callback: CallbackQuery):
    """Отклоняет жалобу"""
    await callback.answer()

    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    complaint_id = int(callback.data.split(":")[1])

    db = SessionLocal()
    try:
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            await callback.message.edit_text("❌ Жалоба не найдена")
            return

        # Обновляем статус жалобы
        complaint.status = "rejected"
        complaint.is_resolved = True
        complaint.resolution = "Жалоба отклонена службой поддержки"
        complaint.reviewed_by = callback.from_user.id
        complaint.reviewed_at = datetime.now()

        db.commit()

        await callback.message.edit_text(
            f"❌ **Жалоба #{complaint_id} отклонена**\n\n"
            "Жалоба была отклонена и закрыта.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Ошибка при отклонении жалобы: {e}")
        await callback.answer("Ошибка при отклонении жалобы")
    finally:
        db.close()


@router.callback_query(F.data.startswith("strike_user:"))
async def strike_user_handler(callback: CallbackQuery):
    """Выдает страйк пользователю"""
    await callback.answer()

    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    target_user_id = int(callback.data.split(":")[1])

    db = SessionLocal()
    try:
        target_user = db.query(User).filter(User.id == target_user_id).first()
        if not target_user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return

        # Увеличиваем количество страйков
        target_user.strikes += 1

        # Проверяем, нужно ли заблокировать пользователя
        if target_user.strikes >= 3:
            target_user.is_banned = True
            ban_message = f"⚠️ **Пользователь заблокирован!**\n\nПользователь {target_user.first_name} получил 3 страйка и был автоматически заблокирован."
        else:
            ban_message = f"⚠️ **Страйк выдан!**\n\nПользователь {target_user.first_name} получил страйк #{target_user.strikes}/3"

        db.commit()

        await callback.message.edit_text(
            ban_message,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Ошибка при выдаче страйка: {e}")
        await callback.answer("Ошибка при выдаче страйка")
    finally:
        db.close()


@router.callback_query(F.data == "back_to_support")
async def back_to_support(callback: CallbackQuery):
    """Возвращает к панели поддержки"""
    await callback.answer()
    await callback.message.edit_text(
        "🆘 **Служба поддержки**\n\n" "Выберите нужный раздел:",
        reply_markup=get_support_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("pending_questions"))
async def show_pending_questions(message: Message):
    """Показывает вопросы в поддержку (только для службы поддержки)"""
    if not has_support_permissions(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    db = SessionLocal()
    try:
        pending_questions = (
            db.query(SupportQuestion).filter(SupportQuestion.status == "pending").all()
        )

        if not pending_questions:
            await message.answer("📋 Нет вопросов в поддержку")
            return

        text = "📋 **Вопросы в поддержку:**\n\n"
        for question in pending_questions[:10]:  # Показываем первые 10
            user = db.query(User).filter(User.id == question.user_id).first()
            user_name = user.first_name if user else "Неизвестно"

            text += f"🔸 **Вопрос #{question.id}**\n"
            text += f"👤 От: {user_name}\n"
            text += f"📅 {question.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"📝 {question.question[:50]}{'...' if len(question.question) > 50 else ''}\n\n"

        if len(pending_questions) > 10:
            text += f"... и еще {len(pending_questions) - 10} вопросов"

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при получении вопросов: {e}")
        await message.answer("❌ Ошибка при получении данных")
    finally:
        db.close()


@router.callback_query(F.data == "pending_questions")
async def show_pending_questions_callback(callback: CallbackQuery):
    """Показывает вопросы в поддержку (только для службы поддержки)"""
    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    db = SessionLocal()
    try:
        pending_questions = (
            db.query(SupportQuestion).filter(SupportQuestion.status == "pending").all()
        )

        if not pending_questions:
            await callback.message.edit_text("📋 Нет вопросов в поддержку")
            return

        text = "📋 **Вопросы в поддержку:**\n\n"
        for question in pending_questions[:10]:  # Показываем первые 10
            user = db.query(User).filter(User.id == question.user_id).first()
            user_name = user.first_name if user else "Неизвестно"

            text += f"🔸 **Вопрос #{question.id}**\n"
            text += f"👤 От: {user_name}\n"
            text += f"📅 {question.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"📝 {question.question[:50]}{'...' if len(question.question) > 50 else ''}\n\n"

        if len(pending_questions) > 10:
            text += f"... и еще {len(pending_questions) - 10} вопросов"

        # Добавляем кнопки для навигации
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_support")]
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при получении вопросов: {e}")
        await callback.answer("Ошибка при получении данных")
    finally:
        db.close()


@router.callback_query(F.data.startswith("answer_question:"))
async def answer_question_handler(callback: CallbackQuery):
    """Показывает детали вопроса для ответа"""
    await callback.answer()

    if not has_support_permissions(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    question_id = int(callback.data.split(":")[1])

    db = SessionLocal()
    try:
        question = (
            db.query(SupportQuestion).filter(SupportQuestion.id == question_id).first()
        )
        if not question:
            await callback.message.edit_text("❌ Вопрос не найден")
            return

        user = db.query(User).filter(User.id == question.user_id).first()
        user_name = user.first_name if user else "Неизвестно"

        text = f"""
❓ **ВОПРОС #{question.id}**

👤 **От:** {user_name} (@{user.username or 'N/A'})
📅 **Дата:** {question.created_at.strftime('%d.%m.%Y %H:%M')}
📊 **Статус:** {question.status}

📝 **Вопрос:**
{question.question}

{('✅ **Ответ:**' + chr(10) + str(question.answer)) if question.answer else ''}
        """.strip()

        # Кнопки для действий с вопросом
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Ответить",
                        callback_data=f"answer_question_form:{question_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад к вопросам", callback_data="pending_questions"
                    ),
                ],
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при получении деталей вопроса: {e}")
        await callback.answer("Ошибка при получении данных")
    finally:
        db.close()


@router.message(Command("answer_question"))
async def answer_question_command(message: Message):
    """Команда для ответа на вопрос (только для службы поддержки)"""
    if not has_support_permissions(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    # Парсим команду: /answer_question ID ответ
    command_parts = message.text.split(" ", 2)
    if len(command_parts) < 3:
        await message.answer(
            "❌ Неверный формат команды.\n" "Используйте: /answer_question ID ответ"
        )
        return

    try:
        question_id = int(command_parts[1])
        answer_text = command_parts[2]

        db = SessionLocal()
        try:
            question = (
                db.query(SupportQuestion)
                .filter(SupportQuestion.id == question_id)
                .first()
            )
            if not question:
                await message.answer("❌ Вопрос не найден")
                return

            # Обновляем вопрос
            question.answer = answer_text
            question.status = "answered"
            question.answered_at = datetime.now()

            db.commit()

            await message.answer(
                f"✅ **Ответ на вопрос #{question_id} отправлен!**\n\n"
                f"📝 Ответ: {answer_text}",
                parse_mode="Markdown",
            )

            # Уведомляем пользователя об ответе
            try:
                from bot.main import bot

                user = db.query(User).filter(User.id == question.user_id).first()
                if user:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"💬 **Получен ответ на ваш вопрос #{question_id}**\n\n"
                        f"📝 Ответ: {answer_text}\n\n"
                        "Спасибо за обращение в поддержку!",
                        parse_mode="Markdown",
                    )
            except Exception as e:
                logger.error(f"Ошибка при уведомлении пользователя: {e}")

        finally:
            db.close()

    except ValueError:
        await message.answer("❌ Неверный ID вопроса")
    except Exception as e:
        logger.error(f"Ошибка при ответе на вопрос: {e}")
        await message.answer("❌ Ошибка при ответе на вопрос")
