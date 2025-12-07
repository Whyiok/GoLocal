import config
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from base import SQL

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ ---
db = SQL('db.db')
bot = Bot(token=config.TOKEN)
dp = Dispatcher()
temp_user_data = {}

logger.info("Бот инициализирован")

# --- ТИПЫ МЕСТ ---
# 1 - ОТЕЛЬ
# 2 - КАФЕ
# 3 - РЕСТОРАН
# 4 - ПРОДУКТОВЫЙ МАГАЗИН
# 5 - ФИРМЕННЫЙ МАГАЗИН (ОПЦИОНАЛЬНО ДЛЯ ГОРОДА)

# --- СТАТУСЫ АДМИНОВ ---
# 1 - ДОБАВЛЕНИЕ ИМЕНИ МЕСТА
# 2 - ДОБАВЛЕНИЕ ТИПА МЕСТА

# --- КЛАВИАТУРЫ ---


# kb_manage — удалён, чтобы не было предупреждений о неинициализированной переменной id_dot
kb_admin = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить место", callback_data="add_dot")],
    [InlineKeyboardButton(text="⚙️ Управлять местами", callback_data="control_dots")]
])

kb_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📍 Места в Красноярске", callback_data="dots_in_krasnoyarsk")],
    [InlineKeyboardButton(text="⭐ Мои места", callback_data="my_dots")],
    [InlineKeyboardButton(text="❤️ Избранные", callback_data="favourite_dots")]
])


# --- ОБРАБОТКА СООБЩЕНИЙ ---
@dp.message()
async def handle_message(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"

    logger.info(f"Сообщение от {username} (ID: {user_id}): {message.text}")

    # Регистрация нового пользователя
    if not db.user_exist(user_id):
        logger.info(f"Новый пользователь: {username} (ID: {user_id})")
        db.add_user(user_id)

    status = db.get_field("users", user_id, "status")
    is_admin = db.get_field("users", user_id, "is_admin")

    logger.debug(f"Пользователь {username}: статус={status}, is_admin={is_admin}")

    # Проверка прав администратора
    if not is_admin:
        logger.info(f"Пользователь {username} открыл главное меню")
        await message.answer("Главное меню:", reply_markup=kb_main)
        return

    # Процесс добавления места - ШАГ 1: Название
    if status == 1:
        name_dot = message.text
        temp_user_data[user_id] = {"name_dot": name_dot}
        next_id = db.get_next_available_id("city_krasnoyarsk")

        logger.info(f"Админ {username} начал добавление места: '{name_dot}' (следующий ID: {next_id})")

        await message.answer(f"✅ Название сохранено\n📝 Следующий ID: {next_id}\n\nВведите тип места:")
        db.update_field("users", user_id, "status", 2)
        return

    # Процесс добавления места - ШАГ 2: Тип
    if status == 2:
        if user_id not in temp_user_data:
            logger.warning(f"Админ {username}: данные утеряны, процесс прерван")
            await message.answer("⚠️ Сессия утеряна. Начните заново.", reply_markup=kb_admin)
            return

        name_dot = temp_user_data[user_id].get("name_dot", "")
        type_dot = message.text

        try:
            actual_id = db.add_dot_krasnoyarsk(name_dot, type_dot)
            logger.info(f"Админ {username} добавил место: ID={actual_id}, name='{name_dot}', type='{type_dot}'")

            db.update_field("users", user_id, "status", 0)
            del temp_user_data[user_id]

            await message.answer(f"✅ Успешно добавлено!\n📍 {name_dot}\n🔢 ID: {actual_id}\n📋 Тип: {type_dot}",
                                 reply_markup=kb_admin)

        except Exception as e:
            logger.error(f"Ошибка при добавлении места админом {username}: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=kb_admin)
        return

    # --- ДОБАВИТЬ В handle_message статус ---
    if status == 101:
        if user_id in temp_user_data and "edit_dot_id" in temp_user_data[user_id]:
            dot_id = temp_user_data[user_id]["edit_dot_id"]
            name_dot = message.text
            db.cursor.execute("UPDATE city_krasnoyarsk SET name_dot = ? WHERE id_dot = ?", (name_dot, dot_id))
            db.connection.commit()
            await message.answer(f"✅ Название успешно изменено на: {name_dot}", reply_markup=kb_admin)
            db.update_field("users", user_id, "status", 0)
            del temp_user_data[user_id]
            return
    if status == 102:
        if user_id in temp_user_data and "edit_dot_id" in temp_user_data[user_id]:
            dot_id = temp_user_data[user_id]["edit_dot_id"]
            type_dot = message.text
            db.cursor.execute("UPDATE city_krasnoyarsk SET type_dot = ? WHERE id_dot = ?", (type_dot, dot_id))
            db.connection.commit()
            await message.answer(f"✅ Тип успешно изменён на: {type_dot}", reply_markup=kb_admin)
            db.update_field("users", user_id, "status", 0)
            del temp_user_data[user_id]
            return

    # Админское меню по умолчанию
    logger.info(f"Админ {username} открыл админ-меню")
    await message.answer("🛠️ Меню администратора:", reply_markup=kb_admin)


# --- ОБРАБОТКА КНОПОК ---
@dp.callback_query()
async def handle_callback(call):
    user_id = call.from_user.id
    username = call.from_user.username or f"user_{user_id}"
    callback_data = call.data

    logger.info(f"Кнопка от {username}: {callback_data}")

    # Регистрация нового пользователя
    if not db.user_exist(user_id):
        logger.info(f"Новый пользователь через кнопку: {username}")
        db.add_user(user_id)

    # Обработка конкретных callback-данных
    if callback_data == "add_dot":
        logger.info(f"Админ {username} начал процесс добавления места")
        await call.answer("✏️ Введите название места")
        db.update_field("users", user_id, "status", 1)
        if user_id in temp_user_data:
            del temp_user_data[user_id]

    elif callback_data == "control_dots":
        dots = db.get_dots("city_krasnoyarsk")
        count = len(dots) if dots else 0
        logger.info(f"Админ {username} запросил управление местами (всего: {count})")

        if dots:
            await call.answer(f"📍 Доступно мест: {count}")
            await call.message.answer("Выберите место:")
            for dot in dots:
                id_dot, name_dot, type_dot = dot[0], dot[1], dot[2]
                buttons = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text='✏️ Изменить название', callback_data=f'edit_name_{id_dot}')],
                        [InlineKeyboardButton(text='🏷️ Изменить тип', callback_data=f'edit_type_{id_dot}')],
                        [InlineKeyboardButton(text='🗑️ Удалить', callback_data=f'delete_{id_dot}')]
                    ]
                )
                await call.message.answer(
                    f"📍 {name_dot} | тип: {type_dot}", reply_markup=buttons
                )
        else:
            await call.answer("❌ Нет доступных мест!")

    # === ДОБАВЛЕНИЕ ОБРАБОТЧИКОВ КНОПОК ===
    elif callback_data.startswith("edit_name_"):
        dot_id = int(callback_data.split("edit_name_")[1])
        db.update_field("users", user_id, "status", 101)
        temp_user_data[user_id] = {"edit_dot_id": dot_id}
        await call.message.answer("✏️ Введите новое название для выбранного места:")
        await call.answer()
    elif callback_data.startswith("edit_type_"):
        dot_id = int(callback_data.split("edit_type_")[1])
        db.update_field("users", user_id, "status", 102)
        temp_user_data[user_id] = {"edit_dot_id": dot_id}
        await call.message.answer("🏷️ Введите новый тип для выбранного места:")
        await call.answer()
    elif callback_data.startswith("delete_"):
        dot_id = int(callback_data.split("delete_")[1])
        db.cursor.execute("DELETE FROM city_krasnoyarsk WHERE id_dot = ?", (dot_id,))
        await bot.delete_message(user_id, call.message.message_id)
        db.connection.commit()

        #(f"🗑️ Место ID {dot_id} удалено!")
        await call.answer()

    elif callback_data == "dots_in_krasnoyarsk":
        dots = db.get_dots("city_krasnoyarsk")
        count = len(dots) if dots else 0
        logger.info(f"Пользователь {username} запросил список мест (найдено: {count})")

        if not dots:
            await call.answer("❌ Нет доступных мест!")
            return

        # Отправляем общее сообщение с количеством
        await call.message.answer(f"📍 Места в Красноярске (всего: {count}):")

        # Отправляем каждое место отдельным сообщением с форматированием
        for dot in dots:
            id_dot, name_dot, type_dot = dot[0], dot[1], dot[2]

            # Преобразование типа в читаемый формат
            type_names = {
                1: "🏨 Отель",
                2: "🍽️ Ресторан",
                3: "🏛️ Достопримечательность"
            }

            type_text = type_names.get(type_dot, f"📋 {type_dot}")

            # Получаем дополнительную статистику, если есть
            additional_info = ""
            if len(dot) > 3:  # Если есть дополнительные поля
                rate = dot[3] if dot[3] else "нет"
                additional_info = f"\n⭐ Рейтинг: {rate}"

            message_text = f"""
📍 ID: {id_dot}
📝 Название: {name_dot}
{type_text}{additional_info}
            """.strip()

            logger.debug(f"Отправка места: ID={id_dot}, name={name_dot}")
            await call.message.answer(message_text)

    elif callback_data == "my_dots":
        logger.info(f"Пользователь {username} запросил 'Мои места'")
        await call.message.answer("⏳ Функционал в разработке")
        await call.answer()

    elif callback_data == "favourite_dots":
        logger.info(f"Пользователь {username} запросил 'Избранные'")
        await call.message.answer("⏳ Функционал в разработке")
        await call.answer()

    else:
        logger.warning(f"Неизвестный callback_data от {username}: {callback_data}")
        await call.answer("❌ Неизвестная команда")


# --- ОБРАБОТКА ОШИБОК ---
@dp.error()
async def error_handler(update, exception):
    logger.error(f"Глобальная ошибка: {exception}", exc_info=True)
    logger.error(f"Update: {update}", exc_info=False)
    return True


# --- ЗАПУСК БОТА ---
async def main():
    logger.info("=== ЗАПУСК БОТА ===")
    logger.info(f"Токен: {config.TOKEN[:10]}...")

    try:
        # Тестовое подключение к БД
        test_dots = db.get_dots("city_krasnoyarsk")
        logger.info(f"Подключение к БД: OK (мест в базе: {len(test_dots) if test_dots else 0})")

        logger.info("Запуск polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Фатальная ошибка: {e}", exc_info=True)
    finally:
        logger.info("=== БОТ ОСТАНОВЛЕН ===")
