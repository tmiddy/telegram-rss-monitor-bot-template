
import telebot
import logging
import time
import re
import os
from urllib.parse import urlparse 
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import threading 

from config import BOT_TOKEN, CHECK_INTERVAL_SECONDS, LOG_LEVEL, MAX_FETCH_ERRORS
from data_manager import DataManager 
from services.link_service import LinkService
from services.subscription_service import SubscriptionService
from services.fetcher_service import FetcherService
from services.parser_service import ParserService
from services.notification_service import NotificationService
from services.app_service import AppService
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s',
    level=getattr(logging, LOG_LEVEL, logging.INFO)
)
logger = logging.getLogger(__name__)

logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.INFO)


# --- Инициализация сервисов ---
data_manager = DataManager() 

link_service = LinkService(data_manager)
subscription_service = SubscriptionService(data_manager)
fetcher_service = FetcherService()
parser_service = ParserService()
notification_service = NotificationService(data_manager)
app_service = AppService(data_manager, link_service, subscription_service)

# --- Клавиатура и тексты кнопок ---
BUTTON_INSTRUCTION = "📄 Инструкция"
BUTTON_MY_LINKS = '📚 Мои ссылки'
BUTTON_SUPPORT = "🛠️ Поддержка"
BUTTON_ADD_TRACKING = "➕ Добавить ссылку"
BUTTON_SUBSCRIPTION = "💳 Пожертвование"

def create_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_instruction = telebot.types.KeyboardButton(BUTTON_INSTRUCTION)
    btn_my_links = telebot.types.KeyboardButton(BUTTON_MY_LINKS)
    btn_support = telebot.types.KeyboardButton(BUTTON_SUPPORT)
    btn_add_tracking = telebot.types.KeyboardButton(BUTTON_ADD_TRACKING)
    btn_subscription = telebot.types.KeyboardButton(BUTTON_SUBSCRIPTION)
    
    markup.add(btn_add_tracking, btn_my_links) 
    markup.add(btn_instruction, btn_support)   
    markup.add(btn_subscription)               
    return markup

main_keyboard = create_main_keyboard()


# --- Инлайн-клавиатура для выбора устройства ---
def create_device_selection_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    btn_phone = InlineKeyboardButton("📱 Телефон", callback_data="instruction_phone")
    btn_pc = InlineKeyboardButton("💻 ПК/Ноутбук", callback_data="instruction_pc")
    markup.add(btn_phone, btn_pc)
    return markup

# --- Monitoring Service (Background Worker) ---
class MonitoringService:
    def __init__(self, bot_instance: telebot.TeleBot, dm: DataManager, fs: FetcherService, ps: ParserService, ns: NotificationService, ls: LinkService):
        self.bot = bot_instance
        self.data_manager = dm
        self.fetcher_service = fs
        self.parser_service = ps
        self.notification_service = ns
        self.link_service = ls 

    def _process_single_link(self, link_info_dict: dict):
        normalized_url = link_info_dict['normalized_url']
        logger.info(f"Checking link: {normalized_url}")

        try:
            content = self.fetcher_service.fetch_url_content(normalized_url)
            if content is None:
                logger.warning(f"Failed to fetch content for link {normalized_url} after retries.")
                self.data_manager.update_link_check_status(normalized_url, error_increment=1)
                link_data_for_deactivation_check = self.data_manager.get_link(normalized_url) 
                if link_data_for_deactivation_check and self.link_service.deactivate_link_due_to_errors(normalized_url, MAX_FETCH_ERRORS): 
                    subscribers = self.data_manager.get_active_subscribers_for_link(normalized_url)
                    original_url_display = link_data_for_deactivation_check.get('original_url_example', normalized_url)
                    for sub_user_info in subscribers:
                        self.notification_service.send_link_deactivated_notification(
                            self.bot, sub_user_info['chat_id'], sub_user_info['user_id'], original_url_display
                        )
                return

            parsed_lots = self.parser_service.parse_rss_feed(content)
            if parsed_lots is None: 
                logger.warning(f"Failed to parse content or feed is empty for link {normalized_url}.")
                self.data_manager.update_link_check_status(normalized_url, success=True) 
                return

            known_guids = self.data_manager.get_known_lot_guids_for_link(normalized_url)
            new_lots_data = [lot for lot in parsed_lots if lot['guid'] not in known_guids]

            if new_lots_data:
                logger.info(f"Found {len(new_lots_data)} new lot(s) for link {normalized_url}.")
                self.data_manager.add_lots_to_known(normalized_url, new_lots_data)
                
                subscribers = self.data_manager.get_active_subscribers_for_link(normalized_url)
                for user_sub_info in subscribers:
                    user_check = self.data_manager.get_user(user_sub_info['user_id'])
                    if user_check and user_check.get('is_active'):
                        for lot_data in new_lots_data:

                            self.notification_service.send_new_lot_notification(
                                self.bot, user_sub_info['chat_id'], user_sub_info['user_id'], lot_data, normalized_url
                            )
                    else:
                        logger.info(f"Skipping notification for inactive user {user_sub_info['user_id']} for link {normalized_url}")
            else:
                logger.debug(f"No new lots for link {normalized_url}.")

            self.data_manager.update_link_check_status(normalized_url, success=True)

        except Exception as e:
            logger.error(f"Unhandled error processing link {normalized_url}: {e}", exc_info=True)
            self.data_manager.update_link_check_status(normalized_url, error_increment=1)

            link_data_for_deactivation_check = self.data_manager.get_link(normalized_url)
            if link_data_for_deactivation_check and self.link_service.deactivate_link_due_to_errors(normalized_url, MAX_FETCH_ERRORS):
                subscribers = self.data_manager.get_active_subscribers_for_link(normalized_url)
                original_url_display = link_data_for_deactivation_check.get('original_url_example', normalized_url)
                for sub_user_info in subscribers:
                    self.notification_service.send_link_deactivated_notification(
                        self.bot, sub_user_info['chat_id'], sub_user_info['user_id'], original_url_display
                    )


    def check_all_active_links(self):
        logger.info("Starting periodic link check job...")
        try:
            active_links_info_list = self.data_manager.get_all_active_subscribed_links_info()
            
            if not active_links_info_list:
                logger.info("No active links with subscriptions to check.")
                return

            logger.info(f"Found {len(active_links_info_list)} active links to check.")
            for link_info_dict in active_links_info_list:

                self._process_single_link(link_info_dict) 
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"Critical error in check_all_active_links job: {e}", exc_info=True)
        finally:
            logger.info("Finished periodic link check job.")

    def populate_initial_lots(self, normalized_url: str):
        try:
            link_data = self.data_manager.get_link(normalized_url)
            if not link_data or not link_data.get('is_active', True):
                logger.warning(f"Cannot populate initial lots for inactive or non-existent link: {normalized_url}")
                return

            logger.info(f"Populating initial lots for link: {normalized_url}")
            content = self.fetcher_service.fetch_url_content(normalized_url)
            if content is None:
                logger.warning(f"Failed to fetch content for initial population of link: {normalized_url}.")
                self.data_manager.update_link_check_status(normalized_url, error_increment=1)
                return

            parsed_lots = self.parser_service.parse_rss_feed(content)
            if parsed_lots is None: 
                logger.warning(f"Failed to parse content for initial population of link: {normalized_url}.")

                return
            
            added_count = self.data_manager.add_lots_to_known(normalized_url, parsed_lots)
            logger.info(f"Initially populated {added_count} lots for link: {normalized_url}.")
            self.data_manager.update_link_check_status(normalized_url, success=True) 
        except Exception as e:
            logger.error(f"Error populating initial lots for link {normalized_url}: {e}", exc_info=True)


# --- Экземпляр бота Telebot ---
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="MarkdownV2")
monitoring_service = MonitoringService(
    bot, data_manager, fetcher_service, parser_service, notification_service, link_service
)

# --- Вспомогательная функция для отправки сообщений с клавиатурой ---
def send_message_with_keyboard(chat_id, text, **kwargs):
    """Отправляет сообщение с основной клавиатурой, обрабатывая ошибки API."""
    try:
        parse_mode = kwargs.pop("parse_mode", None) # Извлекаем parse_mode, если есть
        bot.send_message(chat_id, text, reply_markup=main_keyboard, parse_mode=parse_mode, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Ошибка API Telegram при отправке сообщения в чат {chat_id}: {e}", exc_info=True)
        if "parse error" in str(e).lower() and parse_mode:
            logger.warning(f"Попытка отправить то же сообщение без Markdown в чат {chat_id}")
            try:
                bot.send_message(chat_id, text, reply_markup=main_keyboard, **kwargs) 
            except Exception as e_fallback:
                 logger.error(f"Ошибка при отправке fallback сообщения в чат {chat_id}: {e_fallback}", exc_info=True)
    except Exception as e:
        logger.error(f"Общая ошибка при отправке сообщения в чат {chat_id}: {e}", exc_info=True)


def reply_to_message_with_keyboard(message, text, **kwargs):
    """Отвечает на сообщение с основной клавиатурой, обрабатывая ошибки API."""
    try:
        parse_mode = kwargs.pop("parse_mode", None)
        bot.reply_to(message, text, reply_markup=main_keyboard, parse_mode=parse_mode, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Ошибка API Telegram при ответе на сообщение {message.message_id} в чате {message.chat.id}: {e}", exc_info=True)
        if "parse error" in str(e).lower() and parse_mode:
            logger.warning(f"Попытка ответить тем же текстом без Markdown на сообщение {message.message_id}")
            try:
                bot.reply_to(message, text, reply_markup=main_keyboard, **kwargs) # Без parse_mode
            except Exception as e_fallback:
                 logger.error(f"Ошибка при отправке fallback ответа на сообщение {message.message_id}: {e_fallback}", exc_info=True)

    except Exception as e:
        logger.error(f"Общая ошибка при ответе на сообщение {message.message_id} в чате {message.chat.id}: {e}", exc_info=True)

def send_instruction_photo_safe(chat_id, user_id, photo_file_name, caption):
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        photo_path = os.path.join(base_dir, photo_file_name)

        if not os.path.exists(photo_path):
            
            logger.error(f"File NOT FOUND: {photo_path} for instruction '{caption}'")
            send_message_with_keyboard(chat_id, f"К сожалению, файл инструкции (изображение) '{caption}' сейчас недоступен\\.", parse_mode="MarkdownV2")
            return False

       
        with open(photo_path, 'rb') as photo_file_obj:
            bot.send_photo(chat_id, photo_file_obj, caption=caption, reply_markup=main_keyboard)
        return True
    except telebot.apihelper.ApiTelegramException as e:

        
        send_message_with_keyboard(chat_id, f"Произошла ошибка API при отправке фотоинструкции '{caption}'\\.", parse_mode="MarkdownV2")
        return False
    except FileNotFoundError: 
        logger.error(f"Explicit FileNotFoundError for {photo_path} (should have been caught by os.path.exists). Caption: '{caption}'", exc_info=True)
        send_message_with_keyboard(chat_id, f"Не удалось найти файл для фотоинструкции '{caption}'\\.", parse_mode="MarkdownV2")
        return False
    except Exception as e:
  
        logger.error(f"Generic error sending photo {photo_file_name} to chat {chat_id}: {e}", exc_info=True)
        send_message_with_keyboard(chat_id, f"Произошла непредвиденная ошибка при отправке фото '{caption}'\\.", parse_mode="MarkdownV2")
        return False


# --- Обработчики команд Telebot ---
@bot.message_handler(commands=['start', 'help'])
def handle_start(message: telebot.types.Message):
    response_text = app_service.handle_start_command(message.from_user, message.chat.id)
    bot.reply_to(message, response_text, parse_mode="MARKDOWN", reply_markup=main_keyboard)

@bot.message_handler(commands=['donate'])
def handle_donate(message: telebot.types.Message):
    send_instruction_photo_safe(message.chat.id, message.from_user.id, 'my_QR.png', "`2202206334975815`\nСбер\\)💕")

@bot.message_handler(commands=['add'])
def handle_add_command(message: telebot.types.Message):
    try:

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip(): 
            raise IndexError 
        url_to_add = parts[1].strip()
        
        response_text = app_service.handle_add_link(message.from_user, message.chat.id, url_to_add)
        
        normalized_url = link_service.normalize_url(url_to_add)
        if normalized_url and ("Вы подписались" in response_text or "уже подписаны" in response_text):
            link_data = data_manager.get_link(normalized_url) 
            if link_data and not data_manager.get_known_lot_guids_for_link(normalized_url): 
                logger.info(f"Scheduling initial population for new/renewed subscription (command): {normalized_url}")
                threading.Thread(target=monitoring_service.populate_initial_lots, args=(normalized_url,)).start()
    except IndexError:
        response_text = "Пожалуйста, укажите URL после команды /add\\. Пример: `/add https://example.com`"
    except Exception as e:
        logger.error(f"Error in /add handler: {e}", exc_info=True)
        response_text = "Произошла ошибка при добавлении ссылки\\."
    reply_to_message_with_keyboard(message, response_text)

@bot.message_handler(commands=['alias'])
def handle_alias_cmd(message: telebot.types.Message):
    try:
        args_str = message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) > 1 else ""
        
        alias_args = args_str.strip().split(maxsplit=1) 
        
        response_text = app_service.handle_alias_command(message.from_user, message.chat.id, alias_args)
    except IndexError: 
        response_text = "Пожалуйста, укажите номер ссылки и опционально название алиаса\\. \nПример: `/alias 1 Мой поиск` или `/alias 1` для удаления алиаса\\."
    except Exception as e:
        logger.error(f"Error in /alias handler: {e}", exc_info=True)
        response_text = "Произошла ошибка при установке алиаса\\."
    reply_to_message_with_keyboard(message, response_text)

URL_REGEX = r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?«»“”‘’]))'

@bot.message_handler(func=lambda message: re.match(URL_REGEX, message.text.strip()) is not None and \
                                        not message.text.lower().startswith(("/add", "/remove", "/start", "/help", "/mylinks")) and \
                                        message.text not in [BUTTON_INSTRUCTION, BUTTON_MY_LINKS, BUTTON_SUPPORT, BUTTON_ADD_TRACKING, BUTTON_SUBSCRIPTION])
def handle_url_message(message: telebot.types.Message):
    url_to_add = message.text.strip()

    if message.text.lower().startswith(("/add", "/remove", "/start", "/help", "/mylinks")):
        return 
        
    response_text = app_service.handle_add_link(message.from_user, message.chat.id, url_to_add)
    
    normalized_url = link_service.normalize_url(url_to_add)
    if normalized_url and ("Вы подписались" in response_text or "уже подписаны" in response_text):
        link_data = data_manager.get_link(normalized_url)
        if link_data and not link_data.get("known_lot_guids"):
            logger.info(f"Scheduling initial population for new/renewed subscription (direct URL): {normalized_url}")
            threading.Thread(target=monitoring_service.populate_initial_lots, args=(normalized_url,)).start()
            
    bot.reply_to(message, response_text, reply_markup=main_keyboard)


@bot.message_handler(commands=['mylinks'])
def handle_my_links(message: telebot.types.Message):
    response_text = app_service.handle_my_links(message.from_user, message.chat.id)
    bot.reply_to(message, response_text, disable_web_page_preview=True, reply_markup=main_keyboard)

@bot.message_handler(commands=['remove'])
def handle_remove_link_command(message: telebot.types.Message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
             raise IndexError
        argument = parts[1].strip()
        response_text = app_service.handle_remove_link(message.from_user, message.chat.id, argument)
    except IndexError:
        response_text = "Пожалуйста, укажите URL или номер ссылки для удаления\\. Пример: `/remove 1`"
    except Exception as e:
        logger.error(f"Error in /remove handler: {e}", exc_info=True)
        response_text = "Произошла ошибка при удалении подписки\\."
    reply_to_message_with_keyboard(message, response_text)

# --- Обработчики кнопок ---
@bot.message_handler(func=lambda message: message.text == BUTTON_INSTRUCTION)
def handle_instruction_button(message: telebot.types.Message):
    keyboard = create_device_selection_keyboard()
    bot.reply_to(message, "Выберите ваше устройство:", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == BUTTON_MY_LINKS)
def handle_my_links_button(message: telebot.types.Message):
    handle_my_links(message)


@bot.message_handler(func=lambda message: message.text == BUTTON_SUPPORT)
def handle_support_button(message: telebot.types.Message):
    support_text = (
        "По техническим вопросам обращайтесь в службу [поддержки](https://t.me/TorgiBotSupport)\\, она поможет решить проблемы\\."  # Замените на реальный Telegram аккаунт
    )
    reply_to_message_with_keyboard(message, support_text, parse_mode="MarkdownV2")


@bot.message_handler(func=lambda message: message.text == BUTTON_ADD_TRACKING)
def handle_add_tracking_button(message: telebot.types.Message):
    reply_to_message_with_keyboard(message, "Пожалуйста\\, отправьте ссылку\\, которую вы хотите отслеживать\\.")


@bot.message_handler(func=lambda message: message.text == BUTTON_SUBSCRIPTION)
def handle_subscription_button(message: telebot.types.Message):
    send_instruction_photo_safe(message.chat.id, message.from_user.id, 'my_QR.png', "`2202206334975815`\nСбер\\)💕")


# --- Обработчик для инлайн-кнопок выбора инструкции ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("instruction_"))
def handle_instruction_choice(call: telebot.types.CallbackQuery):

    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id

    try:
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed to edit message reply markup: {e}")





    if call.data == "instruction_phone":
        send_message_with_keyboard(chat_id, "Готовлю инструкцию для телефона\\.\\.\\.")

        send_instruction_photo_safe(chat_id, user_id, 'instruction/instruction_phone_1.png', "Переходим на сайт [torgi\\.gov](https://torgi.gov.ru/new/public)\n\n*1\\.* Нажимаем на кнопку *'Торги'*\\.\n\n*2\\.* Выбираем интересующие вас *категории имущества\\.*\n\nК примеру\\, Земельные участки\\.")
        send_instruction_photo_safe(chat_id, user_id, 'instruction/instruction_phone_2.png', "Нас отправляет на страницу объявление лотов\\.\n\n*3\\.* Выбираем интересующие вас *фильтры*\\.")
        send_instruction_photo_safe(chat_id, user_id, 'instruction/instruction_phone_3.png', "*4\\.* \\(В правом углу страницы\\) Зажимаем пальцем оранжевый значок веб\\-канала\\.\n\n*5\\.* Копируем *адрес ссылки* и отправляем боту\\.\n\nЕсли возникли трудности, обратитесь к [поддержкe\\.](https://t.me/TorgiBotSupport)")

        send_message_with_keyboard(chat_id, "Далее отправьте ссылку в таком ввиде: *`\\/add ссылка`*", parse_mode="MarkdownV2")


    elif call.data == "instruction_pc":
        send_message_with_keyboard(chat_id, "Готовлю инструкцию для ПК\\/Ноутбука\\.\\.\\.")
        send_instruction_photo_safe(chat_id, user_id, 'instruction/instruction_pc_1.jpg', "Переходим на сайт [torgi\\.gov](https://torgi.gov.ru/new/public)\n\n*1\\.* Нажимаем на кнопку *'Торги'*\\.\n\n*2\\.* Выбираем интересующие вас *категории имущества\\.*\n\nК примеру\\, Земельные участки\\.")

        send_instruction_photo_safe(chat_id, user_id, 'instruction/instruction_pc_2.jpg', "Нас отправляет на страницу объявление лотов\n\n*3\\.* Выбираем интересующие вас *фильтры*\\.\n\n*4\\.* Нажимаем *правой кнопкой мыши* на оранжевый значок веб\\-канала\\.\n\n*5\\.* Копируем *адрес ссылки* и отправляем боту\\.\n\nЕсли возникли трудности\\, обратитесь к [поддержкe\\.](https://t.me/TorgiBotSupport)")
           
        send_message_with_keyboard(chat_id, "Далее отправьте ссылку в таком ввиде: *`\\/add ссылка`*", parse_mode="MarkdownV2")

    else:
        logger.warning(f"Unknown callback data in handle_instruction_choice: {call.data}")
        send_message_with_keyboard(chat_id, "Неизвестный выбор\\. Пожалуйста, попробуйте снова\\.", parse_mode="MarkdownV2")


# Обработчик для всех остальных текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_unknown_text(message: telebot.types.Message):
    if re.match(URL_REGEX, message.text.strip()):
        if not message.text.lower().startswith(("/add", "/remove", "/start", "/help", "/mylinks")):
            handle_url_message(message) 
            return
        



    logger.debug(f"Received unhandled text from {message.from_user.id}: {message.text[:50]}")
    bot.reply_to(message, "Неизвестная команда или неверный формат ссылки\\. Используйте /help для списка команд\\.", reply_markup=main_keyboard)


# --- Настройка APScheduler ---


scheduler = BackgroundScheduler(timezone="Europe/Moscow") 
scheduler.add_job(
    monitoring_service.check_all_active_links,
    trigger=IntervalTrigger(seconds=CHECK_INTERVAL_SECONDS),
    id="link_checker_job",
    name="Periodic Link Checker",
    replace_existing=True,
    jitter=60 
)

# --- Основное выполнение ---
if __name__ == '__main__':
    logger.info("Bot starting with JSON data storage...")
    

    def initial_population_task_json():
        logger.info("Performing initial population of lots for existing links on startup (JSON version)...")
        try:

            active_links_infos = data_manager.get_all_active_subscribed_links_info() 
            for link_info_dict in active_links_infos:
                normalized_url = link_info_dict['normalized_url']
                link_data = link_info_dict['data'] # Данные на момент загрузки DataManager
                

                current_link_data = data_manager.get_link(normalized_url)
                if current_link_data and not current_link_data.get("known_lot_guids"): 
                    logger.info(f"Link {normalized_url} has no known lots. Populating initially.")

                    monitoring_service.populate_initial_lots(normalized_url) 
                    time.sleep(1) 
            logger.info("Initial population task (JSON version) finished.")
        except Exception as e:
            logger.error(f"Error during initial population task (JSON version): {e}", exc_info=True)


    initial_population_task_json()

    scheduler.start()
    logger.info(f"Scheduler started. Link check interval: {CHECK_INTERVAL_SECONDS} seconds.")
    
    try:
        logger.info("Starting Telebot infinity_polling...")
        bot.infinity_polling(logger_level=logging.INFO if LOG_LEVEL == "DEBUG" else None, long_polling_timeout=20)
    except Exception as e:
        logger.critical(f"Bot polling failed critically: {e}", exc_info=True)
    finally:
        logger.info("Bot shutting down...")
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler shut down.")