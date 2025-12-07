import config
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from base import SQL

# ==================== КОНСТАНТЫ ====================
ADMIN_STATUS = {
    "ADD_NAME": 1,      # Добавление имени места
    "ADD_TYPE": 2,      # Добавление типа места
    "ADD_ADDRESS": 3,   # Новый шаг
    "ADD_PHOTO": 4,     # Фото теперь 4-й
    "EDIT_NAME": 101,   # Изменение названия
    "EDIT_TYPE": 102    # Изменение типа
}

USER_STATUS = {
    "ADD_REVIEW": 201,  # Ввод отзыва
    "ADD_RATING": 202   # Ввод оценки
}

PLACE_TYPES = {
    1: "🏨 Отель",
    2: "☕ Кафе",
    3: "🏛️ Достопримечательность",
    4: "🛒 Продуктовый магазин",
    5: "🏪 Фирменный магазин"
}

# ==================== НАСТРОЙКА ЛОГГИРОВАНИЯ ====================
def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot_debug.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
db = SQL('db.db')
db.init_tables()
bot = Bot(token=config.TOKEN)
dp = Dispatcher()
user_sessions = {}  # Временные данные пользователей

logger.info("Бот инициализирован")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def delete_message_after(message, delay: int = 5) -> None:
    """Удаляет сообщение через указанное время"""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")

async def send_temporary_message(context, text: str, delay: int = 3, 
                                 reply_markup=None):
    """Отправляет временное сообщение с автоматическим удалением"""
    if hasattr(context, 'message'):
        sent_msg = await context.message.answer(text, reply_markup=reply_markup)
    else:
        sent_msg = await context.answer(text, reply_markup=reply_markup)
    
    asyncio.create_task(delete_message_after(sent_msg, delay))
    return sent_msg

def get_place_type_name(type_id: int) -> str:
    """Возвращает читаемое название типа места"""
    return PLACE_TYPES.get(type_id, f"📋 Тип {type_id}")

def get_user_session(user_id: int) -> dict:
    """Возвращает или создает сессию пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    return user_sessions[user_id]

# ==================== КЛАВИАТУРЫ ====================
def create_admin_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для администратора"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить место", callback_data="add_place")],
        [InlineKeyboardButton(text="⚙️ Управлять местами", callback_data="manage_places")],
        [InlineKeyboardButton(text="📍 Места в Красноярске", callback_data="places_list")],
        [InlineKeyboardButton(text="⭐ Мои места", callback_data="my_places")],
        [InlineKeyboardButton(text="❤️ Избранные", callback_data="favorites")]
    ])

def create_user_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для обычного пользователя"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Места в Красноярске", callback_data="places_list")],
        [InlineKeyboardButton(text="⭐ Мои места", callback_data="my_places")],
        [InlineKeyboardButton(text="❤️ Избранные", callback_data="favorites")]
    ])

def create_place_management_keyboard(place_id: int, is_favorite: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру для управления конкретным местом"""
    fav_text = "💔 Убрать" if is_favorite else "❤️ В избранное"
    fav_callback = f"remove_fav_{place_id}" if is_favorite else f"add_fav_{place_id}"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fav_text, callback_data=fav_callback)],
        [InlineKeyboardButton(text="✅ Посетил", callback_data=f"visited_{place_id}")],
        [InlineKeyboardButton(text="💬 Отзывы", callback_data=f"reviews_{place_id}")]
    ])

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================
@dp.message()
async def handle_message(message):
    """Основной обработчик сообщений"""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    # Регистрация пользователя
    if not db.user_exist(user_id):
        logger.info(f"Новый пользователь: {username}")
        db.add_user(user_id)
    
    status = db.get_field("users", user_id, "status")
    is_admin = db.get_field("users", user_id, "is_admin")
    session = get_user_session(user_id)
    
    # Обработка фото для администратора
    if message.photo and is_admin and status == ADMIN_STATUS["ADD_PHOTO"]:
        await handle_admin_photo(message, user_id, username, session)
        return
    
    # Обработка текстовых сообщений
    if not message.text:
        return
    
    logger.info(f"Сообщение от {username}: {message.text[:50]}...")
    
    # Обработка статусов пользователя
    if status == USER_STATUS["ADD_REVIEW"]:
        await handle_user_review(message, user_id, username, session)
        return
    
    if status == USER_STATUS["ADD_RATING"]:
        await handle_user_rating(message, user_id, username, session)
        return
    
    # Обработка статусов администратора
    if is_admin:
        await handle_admin_status(message, user_id, username, status, session)
        return
    
    # Показать меню для обычного пользователя
    await show_user_menu(message, user_id, session)

# ==================== ОБРАБОТКА ФОТО АДМИНИСТРАТОРА ====================
async def handle_admin_photo(message, user_id: int, username: str, session: dict):
    """Обработка фото при добавлении места администратором"""
    if "place_id" not in session:
        await message.answer("⚠️ Сессия утеряна. Начните заново.", 
                           reply_markup=create_admin_keyboard())
        return
    
    place_id = session["place_id"]
    photo_file_id = message.photo[-1].file_id
    
    try:
        db.update_dot_photo(place_id, photo_file_id)
        logger.info(f"Админ {username} добавил фото к месту {place_id}")
        await message.answer("✅ Фото успешно добавлено!", 
                           reply_markup=create_admin_keyboard())
        db.update_field("users", user_id, "status", 0)
        del user_sessions[user_id]
    except Exception as e:
        logger.error(f"Ошибка добавления фото: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

# ==================== ОБРАБОТКА ОТЗЫВА ПОЛЬЗОВАТЕЛЯ ====================
async def handle_user_review(message, user_id: int, username: str, session: dict):
    """Обработка отзыва пользователя"""
    if "review_place_id" not in session:
        await message.answer("⚠️ Сессия утеряна. Попробуйте снова.")
        return
    
    place_id = session["review_place_id"]
    review_text = message.text
    
    try:
        review_id = db.add_review(user_id, place_id, review_text, rating=None)
        session["review_id"] = review_id
        db.update_field("users", user_id, "status", USER_STATUS["ADD_RATING"])
        
        logger.info(f"Пользователь {username} оставил отзыв о месте {place_id}")
        await send_temporary_message(message, 
                                   "✅ Отзыв сохранён! Теперь поставьте оценку от 1 до 5:", 
                                   delay=10)
    except Exception as e:
        logger.error(f"Ошибка сохранения отзыва: {e}")
        await message.answer("❌ Не удалось сохранить отзыв. Попробуйте позже.")

# ==================== ОБРАБОТКА ОЦЕНКИ ПОЛЬЗОВАТЕЛЯ ====================
async def handle_user_rating(message, user_id: int, username: str, session: dict):
    """Обработка оценки пользователя"""
    if "review_id" not in session:
        await message.answer("⚠️ Сессия утеряна. Попробуйте снова.")
        return
    
    try:
        rating = int(message.text)
        if 1 <= rating <= 5:
            review_id = session["review_id"]
            db.update_review_rating(review_id, rating)
            
            logger.info(f"Пользователь {username} поставил оценку {rating}")
            
            is_admin = db.get_field("users", user_id, "is_admin")
            kb = create_admin_keyboard() if is_admin else create_user_keyboard()
            
            await send_temporary_message(message, 
                                       f"✅ Спасибо! Вы поставили оценку {rating}⭐", 
                                       delay=5, reply_markup=kb)
            
            db.update_field("users", user_id, "status", 0)
            del user_sessions[user_id]
        else:
            await send_temporary_message(message, 
                                       "❌ Оценка должна быть от 1 до 5. Попробуйте снова:", 
                                       delay=5)
    except ValueError:
        await send_temporary_message(message, 
                                   "❌ Пожалуйста, введите число от 1 до 5:", 
                                   delay=5)

# ==================== ОБРАБОТКА СТАТУСОВ АДМИНИСТРАТОРА ====================
async def handle_admin_status(message, user_id: int, username: str, 
                            status: int, session: dict):
    """Обработка различных статусов администратора"""
    
    # Шаг 1: Добавление названия места
    if status == ADMIN_STATUS["ADD_NAME"]:
        session["place_name"] = message.text.strip()
        next_id = db.get_next_available_id("city_krasnoyarsk")
        
        logger.info(f"Админ {username} начал добавление места: '{message.text}'")
        
        await message.answer(
            f"✅ Название сохранено\n📝 Следующий ID: {next_id}\n\n"
            f"Введите тип места (цифра 1-5):\n"
            f"1 - 🏨 Отель\n2 - ☕ Кафе\n3 - 🏛️ Достопримечательность\n"
            f"4 - 🛒 Продуктовый магазин\n5 - 🏪 Фирменный магазин"
        )
        db.update_field("users", user_id, "status", ADMIN_STATUS["ADD_TYPE"])
        return
    
    # Шаг 2: Добавление типа места
    if status == ADMIN_STATUS["ADD_TYPE"]:
        if "place_name" not in session:
            await message.answer("⚠️ Сессия утеряна. Начните заново.", 
                               reply_markup=create_admin_keyboard())
            return
        
        try:
            place_type = int(message.text)
            session["place_type"] = place_type
            await message.answer("Теперь введите адрес места (строкой):")
            db.update_field("users", user_id, "status", ADMIN_STATUS["ADD_ADDRESS"])
        except ValueError:
            await message.answer("❌ Пожалуйста, введите число от 1 до 5")
        except Exception as e:
            logger.error(f"Ошибка при добавлении места: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}", 
                               reply_markup=create_admin_keyboard())
        return
    
    # Шаг 3: Добавление адреса
    if status == ADMIN_STATUS["ADD_ADDRESS"]:
        if "place_name" not in session or "place_type" not in session:
            await message.answer("⚠️ Сессия утеряна. Начните заново.", 
                               reply_markup=create_admin_keyboard())
            return
        
        address = message.text.strip()
        session["place_address"] = address
        place_name = session["place_name"]
        place_type = session["place_type"]
        
        try:
            place_id = db.add_dot_krasnoyarsk(place_name, place_type)
            db.set_dot_address(place_id, address)
            session["place_id"] = place_id
            
            logger.info(f"Админ {username} добавил место: ID={place_id}")
            db.update_field("users", user_id, "status", ADMIN_STATUS["ADD_PHOTO"])
            
            await message.answer(
                f"✅ Место добавлено!\n📍 {place_name}\n🔢 ID: {place_id}\n"
                f"📋 Тип: {get_place_type_name(place_type)}\n📫 Адрес: {address}\n\n"
                f"📸 Отправьте фото для места (или напишите 'пропустить'):"
            )
        except Exception as e:
            logger.error(f"Ошибка при добавлении места: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}", 
                               reply_markup=create_admin_keyboard())
        return
    
    # Шаг 4: Обработка пропуска фото
    if status == ADMIN_STATUS["ADD_PHOTO"]:
        if message.text and message.text.lower() in ['пропустить', 'skip', 'нет']:
            await message.answer("✅ Место создано без фото.", 
                               reply_markup=create_admin_keyboard())
            db.update_field("users", user_id, "status", 0)
            if user_id in user_sessions:
                del user_sessions[user_id]
            return
    
    # Редактирование названия места
    if status == ADMIN_STATUS["EDIT_NAME"]:
        await handle_edit_name(message, user_id, session)
        return
    
    # Редактирование типа места
    if status == ADMIN_STATUS["EDIT_TYPE"]:
        await handle_edit_type(message, user_id, session)
        return
    
    # Показать админ-меню по умолчанию
    await show_admin_menu(message, user_id, session)

# ==================== ФУНКЦИИ РЕДАКТИРОВАНИЯ МЕСТ ====================
async def handle_edit_name(message, user_id: int, session: dict):
    """Обработка изменения названия места"""
    if "edit_place_id" not in session:
        await message.answer("⚠️ Сессия утеряна.", reply_markup=create_admin_keyboard())
        return
    
    place_id = session["edit_place_id"]
    new_name = message.text
    
    try:
        db.cursor.execute("UPDATE city_krasnoyarsk SET name_dot = ? WHERE id_dot = ?", 
                         (new_name, place_id))
        db.connection.commit()
        
        await message.answer(f"✅ Название успешно изменено на: {new_name}", 
                           reply_markup=create_admin_keyboard())
        db.update_field("users", user_id, "status", 0)
        del user_sessions[user_id]
    except Exception as e:
        logger.error(f"Ошибка изменения названия: {e}")
        await message.answer("❌ Не удалось изменить название.")

async def handle_edit_type(message, user_id: int, session: dict):
    """Обработка изменения типа места"""
    if "edit_place_id" not in session:
        await message.answer("⚠️ Сессия утеряна.", reply_markup=create_admin_keyboard())
        return
    
    place_id = session["edit_place_id"]
    
    try:
        new_type = int(message.text)
        db.cursor.execute("UPDATE city_krasnoyarsk SET type_dot = ? WHERE id_dot = ?", 
                         (new_type, place_id))
        db.connection.commit()
        
        await message.answer(f"✅ Тип успешно изменён на: {get_place_type_name(new_type)}", 
                           reply_markup=create_admin_keyboard())
        db.update_field("users", user_id, "status", 0)
        del user_sessions[user_id]
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число от 1 до 5")
    except Exception as e:
        logger.error(f"Ошибка изменения типа: {e}")
        await message.answer("❌ Не удалось изменить тип.")

# ==================== ПОКАЗ МЕНЮ ====================
async def show_admin_menu(message, user_id: int, session: dict):
    """Показать меню администратора"""
    logger.info(f"Админ открыл админ-меню")
    
    # Удалить предыдущее меню
    if "last_menu_message_id" in session:
        try:
            await bot.delete_message(user_id, session["last_menu_message_id"])
        except:
            pass
    
    sent_msg = await message.answer("🛠️ Меню администратора:", 
                                  reply_markup=create_admin_keyboard())
    session["last_menu_message_id"] = sent_msg.message_id

async def show_user_menu(message, user_id: int, session: dict):
    """Показать меню пользователя"""
    logger.info(f"Пользователь открыл главное меню")
    
    if "last_menu_message_id" in session:
        try:
            await bot.delete_message(user_id, session["last_menu_message_id"])
        except:
            pass
    
    sent_msg = await message.answer("Главное меню:", 
                                  reply_markup=create_user_keyboard())
    session["last_menu_message_id"] = sent_msg.message_id

# ==================== ОБРАБОТКА КНОПОК ====================
@dp.callback_query()
async def handle_callback(call):
    """Обработчик callback-запросов"""
    user_id = call.from_user.id
    username = call.from_user.username or f"user_{user_id}"
    callback_data = call.data
    
    logger.info(f"Кнопка от {username}: {callback_data}")
    
    # Регистрация пользователя
    if not db.user_exist(user_id):
        logger.info(f"Новый пользователь через кнопку: {username}")
        db.add_user(user_id)
    
    # Обработка конкретных действий
    if callback_data == "add_place":
        await handle_add_place(call, user_id, username)
    
    elif callback_data == "manage_places":
        await handle_manage_places(call, user_id, username)
    
    elif callback_data == "places_list":
        await handle_places_list(call, user_id, username)
    
    elif callback_data == "my_places":
        await handle_my_places(call, user_id)
    
    elif callback_data == "favorites":
        await handle_favorites(call, user_id)
    
    # Обработка редактирования мест
    elif callback_data.startswith("edit_name_"):
        await handle_edit_name_callback(call, user_id)
    
    elif callback_data.startswith("edit_type_"):
        await handle_edit_type_callback(call, user_id)
    
    elif callback_data.startswith("delete_"):
        await handle_delete_place(call)
    
    # Обработка избранного и отзывов
    elif callback_data.startswith("add_fav_"):
        await handle_add_favorite(call, user_id)
    
    elif callback_data.startswith("remove_fav_"):
        await handle_remove_favorite(call, user_id)
    
    elif callback_data.startswith("visited_"):
        await handle_visited_place(call, user_id)
    
    elif callback_data.startswith("reviews_"):
        await handle_show_reviews(call)

# ==================== ОБРАБОТЧИКИ КНОПОК ====================
async def handle_add_place(call, user_id: int, username: str):
    """Начать процесс добавления места"""
    logger.info(f"Админ {username} начал добавление места")
    await call.answer("✏️ Введите название места")
    db.update_field("users", user_id, "status", ADMIN_STATUS["ADD_NAME"])
    if user_id in user_sessions:
        del user_sessions[user_id]

async def handle_manage_places(call, user_id: int, username: str):
    """Управление местами"""
    places = db.get_dots("city_krasnoyarsk")
    count = len(places) if places else 0
    logger.info(f"Админ {username} запросил управление местами (всего: {count})")
    
    if not places:
        await call.answer("❌ Нет доступных мест!")
        return
    
    await call.answer(f"📍 Доступно мест: {count}")
    
    try:
        await call.message.delete()
    except:
        pass
    
    for place in places:
        place_id, name, place_type = place[0], place[1], place[2]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✏️ Изменить название', 
                                callback_data=f'edit_name_{place_id}')],
            [InlineKeyboardButton(text='🏷️ Изменить тип', 
                                callback_data=f'edit_type_{place_id}')],
            [InlineKeyboardButton(text='🗑️ Удалить', 
                                callback_data=f'delete_{place_id}')]
        ])
        
        await call.message.answer(
            f"📍 {name} | тип: {get_place_type_name(place_type)}",
            reply_markup=keyboard
        )

async def handle_places_list(call, user_id: int, username: str):
    """Показать список мест"""
    places = db.get_dots("city_krasnoyarsk")
    count = len(places) if places else 0
    logger.info(f"Пользователь {username} запросил список мест (найдено: {count})")
    
    if not places:
        await call.answer("❌ Нет доступных мест!")
        return
    
    try:
        await call.message.delete()
    except:
        pass
    
    for place in places:
        place_id, name, place_type = place[0], place[1], place[2]
        
        # Получить фото
        photo_id = place[3] if len(place) > 3 and place[3] else None
        if not photo_id:
            photo_id = db.get_dot_photo(place_id)
        
        # Проверить избранное
        is_fav = db.is_favourite(user_id, place_id)
        
        # Получить количество отзывов
        reviews = db.get_dot_reviews(place_id)
        reviews_count = len(reviews)
        
        # Получить адрес
        address = db.get_dot_address(place_id) or '—'
        
        # Получить среднюю оценку
        ratings = [r[2] for r in reviews if r[2] is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
        
        # Создать сообщение
        message_text = f"📝 {name}\n{get_place_type_name(place_type)}\n"
        message_text += f"📫 Адрес: {address}\n"
        if avg_rating:
            message_text += f"⭐ Средняя оценка: {avg_rating:.1f}/5.0   "
        message_text += f"💬 Отзывов: {reviews_count}\n"
        
        # Создать клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💔 Убрать" if is_fav else "❤️ В избранное",
                callback_data=f"remove_fav_{place_id}" if is_fav else f"add_fav_{place_id}"
            )],
            [InlineKeyboardButton(text="✅ Посетил", 
                                callback_data=f"visited_{place_id}")],
            [InlineKeyboardButton(text=f"💬 Отзывы ({reviews_count})", 
                                callback_data=f"reviews_{place_id}")]
        ])
        
        # Отправить сообщение
        try:
            if photo_id:
                await call.message.answer_photo(
                    photo=photo_id,
                    caption=message_text,
                    reply_markup=keyboard
                )
            else:
                await call.message.answer(message_text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отправки места {place_id}: {e}")
            await call.message.answer(message_text, reply_markup=keyboard)

async def handle_my_places(call, user_id: int):
    """Показать 'Мои места'"""
    places = db.get_dots("city_krasnoyarsk")
    
    if not places:
        await call.answer("❌ У вас еще нет сохраненных мест")
        return
    
    try:
        await call.message.delete()
    except:
        pass
    
    for place in places:
        place_id, name, place_type = place[0], place[1], place[2]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Добавить в Мои", 
                                callback_data=f"add_my_{place_id}")],
            [InlineKeyboardButton(text="❌ Удалить из Моих", 
                                callback_data=f"remove_my_{place_id}")]
        ])
        
        await call.message.answer(
            f"📍 {name}\n{get_place_type_name(place_type)}",
            reply_markup=keyboard
        )
    
    await call.answer()

async def handle_favorites(call, user_id: int):
    """Показать избранные места"""
    fav_places = db.get_favourite_dots(user_id)
    
    if not fav_places:
        await call.answer("❌ У вас еще нет избранных мест")
        return
    
    try:
        await call.message.delete()
    except:
        pass
    
    for place in fav_places:
        place_id, name, place_type = place[0], place[1], place[2]
        
        # Получить фото
        photo_id = place[3] if len(place) > 3 and place[3] else None
        if not photo_id:
            photo_id = db.get_dot_photo(place_id)
        
        # Получить количество отзывов
        reviews = db.get_dot_reviews(place_id)
        reviews_count = len(reviews)
        
        # Получить адрес
        address = db.get_dot_address(place_id) or '—'
        
        # Получить среднюю оценку
        ratings = [r[2] for r in reviews if r[2] is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
        
        message_text = f"📝 {name}\n{get_place_type_name(place_type)}\n"
        message_text += f"📫 Адрес: {address}\n"
        if avg_rating:
            message_text += f"⭐ Средняя оценка: {avg_rating:.1f}/5.0   "
        message_text += f"💬 Отзывов: {reviews_count}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💔 Убрать из избранного", 
                                callback_data=f"remove_fav_{place_id}")],
            [InlineKeyboardButton(text="✅ Посетил", 
                                callback_data=f"visited_{place_id}")],
            [InlineKeyboardButton(text=f"💬 Отзывы ({reviews_count})", 
                                callback_data=f"reviews_{place_id}")]
        ])
        
        try:
            if photo_id:
                await call.message.answer_photo(
                    photo=photo_id,
                    caption=message_text,
                    reply_markup=keyboard
                )
            else:
                await call.message.answer(message_text, reply_markup=keyboard)
        except:
            await call.message.answer(message_text, reply_markup=keyboard)
    
    await call.answer()

# ==================== ОБРАБОТКА РЕДАКТИРОВАНИЯ ====================
async def handle_edit_name_callback(call, user_id: int):
    """Начать изменение названия места"""
    place_id = int(call.data.split("edit_name_")[1])
    db.update_field("users", user_id, "status", ADMIN_STATUS["EDIT_NAME"])
    user_sessions[user_id] = {"edit_place_id": place_id}
    await send_temporary_message(call, "✏️ Введите новое название:", delay=5)
    await call.answer()

async def handle_edit_type_callback(call, user_id: int):
    """Начать изменение типа места"""
    place_id = int(call.data.split("edit_type_")[1])
    db.update_field("users", user_id, "status", ADMIN_STATUS["EDIT_TYPE"])
    user_sessions[user_id] = {"edit_place_id": place_id}
    await send_temporary_message(call, "🏷️ Введите новый тип (1-5):", delay=5)
    await call.answer()

async def handle_delete_place(call):
    """Удалить место"""
    place_id = int(call.data.split("delete_")[1])
    
    try:
        db.cursor.execute("DELETE FROM city_krasnoyarsk WHERE id_dot = ?", (place_id,))
        db.connection.commit()
        
        try:
            await call.message.delete()
        except:
            pass
        
        await call.answer(f"🗑️ Место ID {place_id} удалено!")
    except Exception as e:
        logger.error(f"Ошибка удаления места {place_id}: {e}")
        await call.answer("❌ Не удалось удалить место")

# ==================== ОБРАБОТКА ИЗБРАННОГО И ОТЗЫВОВ ====================
async def handle_add_favorite(call, user_id: int):
    """Добавить место в избранное"""
    place_id = int(call.data.split("add_fav_")[1])
    
    if db.add_to_favourites(user_id, place_id):
        await call.answer("❤️ Добавлено в избранное!")
    else:
        await call.answer("⚠️ Уже в избранном")

async def handle_remove_favorite(call, user_id: int):
    """Убрать место из избранного"""
    place_id = int(call.data.split("remove_fav_")[1])
    db.remove_from_favourites(user_id, place_id)
    await call.answer("💔 Удалено из избранного")

async def handle_visited_place(call, user_id: int):
    """Обработка нажатия 'Посетил'"""
    place_id = int(call.data.split("visited_")[1])
    
    if db.has_user_reviewed(user_id, place_id):
        await call.answer("ℹ️ Вы уже оставляли отзыв об этом месте")
    else:
        db.update_field("users", user_id, "status", USER_STATUS["ADD_REVIEW"])
        user_sessions[user_id] = {"review_place_id": place_id}
        await send_temporary_message(call, "✍️ Напишите ваш отзыв об этом месте:", delay=10)
        await call.answer()

async def handle_show_reviews(call):
    """Показать отзывы о месте"""
    place_id = int(call.data.split("reviews_")[1])
    reviews = db.get_dot_reviews(place_id, limit=20)
    
    # Получить информацию о месте
    place_info = db.get_dots("city_krasnoyarsk", id_dot=place_id)
    place_name = place_info[0][1] if place_info else f"Место #{place_id}"
    
    if not reviews:
        await call.message.answer(f"💬 Отзывы о месте '{place_name}':\n\n❌ Пока нет отзывов.")
        await call.answer()
        return
    
    # Вычислить среднюю оценку
    ratings = [r[2] for r in reviews if r[2] is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    # Сформировать сообщение
    message_text = f"💬 Отзывы о месте '{place_name}':\n"
    if avg_rating > 0:
        message_text += f"⭐ Средняя оценка: {avg_rating:.1f}/5.0 ({len(ratings)} оценок)\n\n"
    else:
        message_text += f"📊 Всего отзывов: {len(reviews)}\n\n"
    
    # Добавить отзывы
    for idx, review in enumerate(reviews, 1):
        review_text, rating, created_at = review[1], review[2], review[3]
        
        date_str = created_at[:10] if created_at else "неизвестно"
        rating_str = f"⭐ {rating}/5" if rating else "⭐ Нет оценки"
        
        message_text += f"{idx}. {rating_str}\n"
        message_text += f"   {review_text}\n"
        message_text += f"   📅 {date_str}\n\n"
        
        # Разбить длинные сообщения
        if len(message_text) > 3000:
            await call.message.answer(message_text[:3000])
            message_text = message_text[3000:]
    
    if message_text.strip():
        await call.message.answer(message_text)
    
    await call.answer()

# ==================== ОБРАБОТКА ОШИБОК ====================
@dp.error()
async def error_handler(update, exception):
    """Глобальный обработчик ошибок"""
    logger.error(f"Глобальная ошибка: {exception}", exc_info=True)
    return True

# ==================== ЗАПУСК БОТА ====================
async def main():
    """Основная функция запуска бота"""
    logger.info("=== ЗАПУСК БОТА ===")
    logger.info(f"Токен: {config.TOKEN[:10]}...")
    
    try:
        # Проверка подключения к БД
        places = db.get_dots("city_krasnoyarsk")
        logger.info(f"Подключение к БД: OK (мест в базе: {len(places) if places else 0})")
        
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