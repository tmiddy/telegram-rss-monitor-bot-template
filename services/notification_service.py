
import logging
import telebot 
from data_manager import DataManager 
from typing import Dict, Optional
import re 

logger = logging.getLogger(__name__)

MARKDOWN_V2_SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!" 
MARKDOWN_V2_ESCAPE_REGEX = re.compile(f'([{re.escape(MARKDOWN_V2_SPECIAL_CHARS)}])')

def extrac_cadastral_number(text: str) -> str:
    pattern = r"\b\d{2}:\d{2}:\d{6,8}:\d{1,5}\b"
    cadastral_number = re.search(pattern, text)
    if cadastral_number:
        return f"{cadastral_number.group(0)}"
    else:
        return None

def escape_markdown_v2(text: str) -> str:
    if not text:
        return ''
    return MARKDOWN_V2_ESCAPE_REGEX.sub(r'\\\1', text)


class NotificationService:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def send_new_lot_notification(self, bot_instance: telebot.TeleBot, chat_id: int, user_id: int, lot_data: Dict[str, str], source_url_normalized: str): 
        try:
            title_original = lot_data.get('title', 'N/A')
            lot_url_original = lot_data.get('url', '#') 
            description = lot_data.get('description', None)
            if description:
                cadastral_number = extrac_cadastral_number(description)
            else:
                cadastral_number = None

            if len(title_original) > 300: 
                title_original = title_original[:300] + "..."
            
            escaped_title = escape_markdown_v2(title_original)
            
            user_alias = self.data_manager.get_subscription_alias(user_id, source_url_normalized)
            link_identifier_line = ""
            if user_alias:
                link_identifier_line = f"🏷️ *{escape_markdown_v2(user_alias)}*\n" 
            else:
                link_info = self.data_manager.get_link(source_url_normalized)
                if link_info and link_info.get('original_url_example'):
                    url_display_part = link_info['original_url_example']
                    if len(url_display_part) > 70: 
                        url_display_part = url_display_part[:67] + "..."
                    link_identifier_line = f"🏷️ `{escape_markdown_v2(url_display_part)}`\n" 

            href_source_url = source_url_normalized.replace('amp%3B', '&') 
            href_lot_url = lot_url_original.replace('amp%3B', '&')

            cadastral_number_link_display_text_MAPRU = ""
            cadastral_number_link_display_text_KadastrRu = ""
            if cadastral_number:
                safe_cadastral_number = cadastral_number.replace(':', '%3A')
                cadastral_number_url_MAPRU = f"https://map.ru/pkk?kad={safe_cadastral_number}&z=17"
                cadastral_number_url_KADASSTRU = f"https://links.kadastrru.info/objects/find?cadnum={safe_cadastral_number}&type=parcel"
                cadastral_number_link_display_text_MAPRU = f"🏠 [{escape_markdown_v2('MapRu')}]({cadastral_number_url_MAPRU})"
                cadastral_number_link_display_text_KadastrRu = f"[{escape_markdown_v2(' KadastrRU')}]({cadastral_number_url_KADASSTRU})"

            source_link_display_text = escape_markdown_v2("Источник RSS")
            lot_link_display_text = escape_markdown_v2("Подробнее о лоте")

            message_text = (
                f"🔔 *{escape_markdown_v2('Новый лот!')}*\n"
                f"{link_identifier_line}\n" 
                f"🏷️ *{escape_markdown_v2('Название:')}* {escaped_title}\n"
                f"🔗 [{source_link_display_text}]({href_source_url})\n" 
                f"👉 [{lot_link_display_text}]({href_lot_url})\n"
                f"{cadastral_number_link_display_text_MAPRU}"
                f"{cadastral_number_link_display_text_KadastrRu}"
            )
            
            logger.debug(f"USER_ID {user_id} - Original Title: '{title_original}'")
            logger.debug(f"USER_ID {user_id} - Source URL Normalized: '{source_url_normalized}'")
            logger.debug(f"USER_ID {user_id} - Alias: '{user_alias}'")
            logger.info(f"USER_ID {user_id} - ПОПЫТКА ОТПРАВКИ СООБЩЕНИЯ С ССЫЛКАМИ (MarkdownV2):\n{message_text}")

            bot_instance.send_message(chat_id, message_text, parse_mode="MarkdownV2", disable_web_page_preview=True)
            logger.info(f"Sent notification with links for lot: {title_original[:50]}...")

        except telebot.apihelper.ApiTelegramException as e:
            error_description = e.description if hasattr(e, 'description') else str(e)
            error_json = e.result_json if hasattr(e, 'result_json') else {}
            logger.error(
                f"Telegram API error sending notification (WITH LINKS) to chat {chat_id} (user {user_id}): {error_description} (Code: {e.error_code}) - JSON: {error_json}"
            )
            if e.error_code == 403 or (error_json and error_json.get("description", "").lower().count("bot was blocked by the user")):
                logger.warning(f"User {user_id} (chat {chat_id}) blocked the bot. Deactivating user.")
                self.data_manager.set_user_active_status(user_id, False)
            elif e.error_code == 400 and (error_json and error_json.get("description", "").lower().count("chat not found")):
                 logger.warning(f"Chat {chat_id} (user {user_id}) not found. Deactivating user.")
                 self.data_manager.set_user_active_status(user_id, False)
        except Exception as e:
            logger.error(f"Unexpected error sending notification (WITH LINKS) to chat {chat_id} (user {user_id}): {e}", exc_info=True)
    
    def send_link_deactivated_notification(self, bot_instance: telebot.TeleBot, chat_id: int, user_id: int, link_url: str):
        try:
            link_url_for_code_block = link_url.replace('`', '\'') 
            
            text_header = escape_markdown_v2("Ссылка деактивирована!")
            text_part1 = escape_markdown_v2("Ссылка ")
            text_part2 = escape_markdown_v2(" была деактивирована из-за слишком большого количества ошибок при проверке или стала недоступна.")
            text_part3 = escape_markdown_v2("Вы больше не будете получать уведомления по ней, пока ошибка не будет устранена и ссылка не будет добавлена заново.")

            message_text = (
                f"⚠️ *{text_header}*\n\n"
                f"{text_part1}`{link_url_for_code_block}`{text_part2}\n"
                f"{text_part3}"
            )
            bot_instance.send_message(chat_id, message_text, parse_mode="MarkdownV2")
            logger.info(f"Sent link deactivation notice to chat {chat_id} (user {user_id}) for link: {link_url}")
        except Exception as e:
             logger.error(f"Error sending link deactivation notice to chat {chat_id} (user {user_id}): {e}", exc_info=True)