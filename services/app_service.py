
import logging
from typing import Optional, Dict, List, Tuple
from data_manager import DataManager
from services.link_service import LinkService
from services.subscription_service import SubscriptionService
from telebot.types import User as TeleUser 
import telebot 

logger = logging.getLogger(__name__)

class AppService:
    def __init__(self, data_manager: DataManager, link_service: LinkService, sub_service: SubscriptionService):
        self.data_manager = data_manager
        self.link_service = link_service
        self.sub_service = sub_service

    def handle_start_command(self, tele_user: TeleUser, chat_id: int) -> str:
        self.data_manager.get_or_create_user(tele_user.id, chat_id, tele_user.first_name, tele_user.username)
        button_add_tracking_text = "➕ Добавить ссылку"
        button_my_links_text = '📚 Мои ссылки'
        button_instruction_text = "📄 Инструкция"
        button_support_text = "🛠️ Поддержка"
        button_subscription_text = "💳 Пожертвование"
        
        return ("Привет! Я бот для отслеживания новых лотов\n\n"
                "Отправь мне ссылку, чтобы начать отслеживание\n\n"
                "*Команды:*\n"
                "/add *<ссылка>* - Добавить ссылку (или просто отправьте ссылку)\n"
                "/mylinks - Показать ваши текущие подписки\n"
                "/remove *<номер ссылки>* - Удалить подписку\n"
                "/help - Показать это сообщение\n"
                "/alias *<номер ссылки> <название алиаса>* - Установить кароткое название для ссылки\n"
                "/donate - Пожертвовать денег💕\n\n"
                "*Кнопки:*\n"
                f"📌 *{button_add_tracking_text}* - Добавить новую RSS-ссылку для отслеживания.\n"
                f"📌 *{button_my_links_text}* - Просмотреть список ваших отслеживаемых ссылок (или команда /mylinks).\n"
                f"📌 *{button_instruction_text}* - Видеоинструкция по работе с ботом.\n"
                f"📌 *{button_support_text}* - Связаться с поддержкой.\n"
                f"📌 *{button_subscription_text}* - Пожертвовать денег.\n"
                )

    def handle_add_link(self, tele_user: TeleUser, chat_id: int, url_to_add: str) -> str:
        self.data_manager.get_or_create_user(tele_user.id, chat_id, tele_user.first_name, tele_user.username)
        
        normalized_url = self.link_service.normalize_url(url_to_add)
        if not normalized_url:
            return f"Не удалось распознать или нормализовать URL: {telebot.util.escape(url_to_add)}\\. Убедитесь, что это корректная ссылка\\."

        self.link_service.add_new_link(normalized_url, url_to_add) 

        if self.sub_service.add_user_subscription(tele_user.id, normalized_url):
            return f"Вы подписались на отслеживание ссылки:\n`{telebot.util.escape(normalized_url)}`"
        else:
            subs = self.sub_service.get_user_subscriptions_display(tele_user.id)
            if any(s['normalized_url'] == normalized_url for s in subs):
                 return f"Вы уже подписаны на эту ссылку:\n`{telebot.util.escape(normalized_url)}`"
            return f"Произошла ошибка при добавлении подписки на ссылку:\n`{telebot.util.escape(normalized_url)}`"
    
    def handle_my_links(self, tele_user: TeleUser, chat_id: int) -> str:
        self.data_manager.get_or_create_user(tele_user.id, chat_id, tele_user.first_name, tele_user.username)
        subscriptions_display = self.sub_service.get_user_subscriptions_display(tele_user.id)
        
        if not subscriptions_display:
            return "У вас пока нет активных подписок\\."

        response_lines = ["*Ваши активные подписки:*"]
        for sub_info in subscriptions_display:
            escaped_display_url = telebot.util.escape(sub_info['display_url'])
            alias_str = ""
            if sub_info.get('alias'):
                escaped_alias = telebot.util.escape(sub_info['alias'])
                alias_str = f" *{escaped_alias}* " 
            response_lines.append(f"{sub_info['index']}\\.{alias_str} `{escaped_display_url}`")
        return "\n".join(response_lines)

    def handle_remove_link(self, tele_user: TeleUser, chat_id: int, argument: str) -> str:
        self.data_manager.get_or_create_user(tele_user.id, chat_id, tele_user.first_name, tele_user.username)
        subscriptions_display = self.sub_service.get_user_subscriptions_display(tele_user.id)

        if not subscriptions_display:
            return "У вас нет подписок для удаления\\."

        url_to_remove: Optional[str] = None
        display_url_for_message = argument 

        if argument.isdigit():
            try:
                index_to_find = int(argument)
                found_sub = next((s for s in subscriptions_display if s['index'] == index_to_find), None)
                if found_sub:
                    url_to_remove = found_sub['normalized_url']
                    display_url_for_message = found_sub['display_url']
                else:
                    return "Неверный номер ссылки\\. Посмотрите список в /mylinks\\."
            except ValueError:
                return "Неверный формат номера ссылки\\."
        else: 
            normalized_arg_url = self.link_service.normalize_url(argument)
            if not normalized_arg_url:
                found_sub_by_display_url = next((s for s in subscriptions_display if s['display_url'] == argument), None)
                if found_sub_by_display_url:
                    url_to_remove = found_sub_by_display_url['normalized_url']
                    display_url_for_message = found_sub_by_display_url['display_url']
                else:
                    return "Не удалось распознать URL для удаления или найти его в ваших подписках\\. Попробуйте указать номер из /mylinks\\."
            else: 
                found_sub_by_url = next((s for s in subscriptions_display if s['normalized_url'] == normalized_arg_url), None)
                if found_sub_by_url:
                    url_to_remove = normalized_arg_url
                    display_url_for_message = found_sub_by_url['display_url'] 
                else:
                    return "Вы не подписаны на такую ссылку\\."
        
        if url_to_remove and self.sub_service.remove_user_subscription(tele_user.id, url_to_remove):
            escaped_display_url = telebot.util.escape(display_url_for_message)
            return f"Подписка на `{escaped_display_url}` удалена\\."
        else: 
            if url_to_remove: 
                 return f"Не удалось удалить подписку на `{telebot.util.escape(display_url_for_message)}`\\. Попробуйте еще раз или обратитесь в поддержку\\."
            return "Не удалось удалить подписку\\. Убедитесь, что вы указали правильный номер или URL из списка /mylinks\\."

    def handle_alias_command(self, tele_user: TeleUser, chat_id: int, arguments: List[str]) -> str:
        self.data_manager.get_or_create_user(tele_user.id, chat_id, tele_user.first_name, tele_user.username)
        
        if not (1 <= len(arguments) <= 2):
            return "Неверный формат команды\\. Используйте: `/alias <номер ссылки> <название алиаса>` или `/alias <номер ссылки>` для удаления алиаса\\."

        subscription_index_str = arguments[0]
        alias_name: Optional[str] = None
        if len(arguments) == 2:
            alias_name = arguments[1].strip()
            if not alias_name: 
                alias_name = None
            elif len(alias_name) > 50: 
                return "Название алиаса слишком длинное (максимум 50 символов)\\."
        

        current_subscriptions = self.sub_service.get_user_subscriptions_display(tele_user.id)
        if not current_subscriptions:
            return "У вас нет подписок для установки алиаса\\."

        if not subscription_index_str.isdigit():
            return "Номер ссылки должен быть числом\\. Посмотрите список в /mylinks\\."
        
        success, norm_url, display_url = self.sub_service.set_alias_for_subscription(
            tele_user.id, 
            subscription_index_str, 
            alias_name, 
            current_subscriptions
        )

        if success and norm_url and display_url:
            escaped_display_url = telebot.util.escape(display_url)
            if alias_name:
                escaped_alias = telebot.util.escape(alias_name)
                return f"Алиас '{escaped_alias}' установлен для ссылки `{escaped_display_url}`\\."
            else:
                return f"Алиас для ссылки `{escaped_display_url}` удален\\."
        else:
            return "Не удалось установить или удалить алиас\\. Убедитесь, что номер ссылки верный, и попробуйте снова\\."