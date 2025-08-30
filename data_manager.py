
import json
import os
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

USER_DATA_FILE = "user_data.json"
LINK_DATA_FILE = "link_data.json"


user_data_lock = threading.Lock()
link_data_lock = threading.Lock()

def load_json_data(filename: str, lock: threading.Lock) -> Dict:
    with lock:
        if not os.path.exists(filename):
            logger.info(f"File {filename} not found, will create on first save.")
            return {}
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {filename}. Returning empty data.")
            backup_filename = filename + ".corrupted_" + datetime.now().strftime("%Y%m%d%H%M%S")
            try:
                if os.path.exists(filename): 
                     os.rename(filename, backup_filename)
                     logger.info(f"Corrupted file backed up to {backup_filename}")
            except Exception as e_bkp:
                logger.error(f"Could not backup corrupted file {filename}: {e_bkp}")
            return {}
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return {}

def save_json_data(filename: str, data: Dict, lock: threading.Lock):
    with lock:
        try:
            temp_filename = filename + ".tmp"
            with open(temp_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(temp_filename, filename) 
            logger.debug(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving data to {filename}: {e}")
            if os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except Exception as e_rem:
                    logger.error(f"Could not remove temp file {temp_filename}: {e_rem}")


class DataManager:
    def __init__(self):

        self.user_data = load_json_data(USER_DATA_FILE, user_data_lock)
        self.link_data = load_json_data(LINK_DATA_FILE, link_data_lock)

    def _get_current_utc_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _ensure_subscription_format_for_user(self, user_id_str: str, current_user_data: Dict) -> bool:

        user = current_user_data.get(user_id_str)
        if not user:
            return False
        
        subscriptions = user.get("subscriptions")
        if not subscriptions: 
            user["subscriptions"] = []
            return False 

        if isinstance(subscriptions, list) and len(subscriptions) > 0 and isinstance(subscriptions[0], str):
            logger.info(f"Converting subscriptions format for user {user_id_str} from List[str] to List[Dict]")
            user["subscriptions"] = [{"url": u, "alias": None} for u in subscriptions]
            return True
        elif isinstance(subscriptions, list) and \
             all(isinstance(s, dict) and "url" in s for s in subscriptions):
            return False 
        elif isinstance(subscriptions, list) and not subscriptions:
             return False
        else:
         
            logger.warning(f"User {user_id_str} has subscriptions in an unexpected format: {type(subscriptions)}. Resetting to empty list.")
            user["subscriptions"] = []
            return True 

    # --- Методы для пользователей ---
    def get_or_create_user(self, user_id: int, chat_id: int, first_name: Optional[str], username: Optional[str]) -> Dict:
        user_id_str = str(user_id)
       
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)
        
        needs_save = False
        if user_id_str not in current_user_data:
            current_user_data[user_id_str] = {
                "chat_id": chat_id,
                "first_name": first_name,
                "username": username,
                "is_active": True,
                "subscriptions": [],
                "joined_at": self._get_current_utc_iso()
            }
            needs_save = True
            logger.info(f"New user created: {user_id_str}")
        else: 
            user = current_user_data[user_id_str]
            if user.get("first_name") != first_name or \
               user.get("username") != username or \
               not user.get("is_active", True) or \
               user.get("chat_id") != chat_id : 
                user["first_name"] = first_name
                user["username"] = username
                user["is_active"] = True
                user["chat_id"] = chat_id 
                needs_save = True
                logger.info(f"User {user_id_str} data updated and activated.")

            if self._ensure_subscription_format_for_user(user_id_str, current_user_data):
                needs_save = True
        
        if needs_save:
            save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
        self.user_data = current_user_data 
        return current_user_data[user_id_str]

    def get_user(self, user_id: int) -> Optional[Dict]:
       
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)
        self.user_data = current_user_data
        return current_user_data.get(str(user_id))
    
    def set_user_active_status(self, user_id: int, is_active: bool):
        user_id_str = str(user_id)
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)
        if user_id_str in current_user_data:
            if current_user_data[user_id_str]["is_active"] != is_active:
                current_user_data[user_id_str]["is_active"] = is_active
                save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
                self.user_data = current_user_data
                logger.info(f"User {user_id_str} active status set to {is_active}")

     # --- Методы для ссылок ---
    def get_or_create_link(self, normalized_url: str, original_url_example: str) -> Dict:
        current_link_data = load_json_data(LINK_DATA_FILE, link_data_lock)
        needs_save = False
        if normalized_url not in current_link_data:
            current_link_data[normalized_url] = {
                "original_url_example": original_url_example,
                "last_checked": None,
                "error_count": 0,
                "is_active": True,
                "known_lot_guids": [],
                "added_at": self._get_current_utc_iso()
            }
            needs_save = True
            logger.info(f"New link created: {normalized_url}")
        elif not current_link_data[normalized_url].get("is_active", True): 
            current_link_data[normalized_url]["is_active"] = True
            current_link_data[normalized_url]["error_count"] = 0
            
            current_link_data[normalized_url]["original_url_example"] = original_url_example 
            needs_save = True
            logger.info(f"Link {normalized_url} reactivated.")
        
        if needs_save:
            save_json_data(LINK_DATA_FILE, current_link_data, link_data_lock)
        self.link_data = current_link_data
        return current_link_data[normalized_url]

    def get_link(self, normalized_url: str) -> Optional[Dict]:
        current_link_data = load_json_data(LINK_DATA_FILE, link_data_lock)
        self.link_data = current_link_data
        return current_link_data.get(normalized_url)

    def get_all_active_subscribed_links_info(self) -> List[Dict[str, Any]]:
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)
        current_link_data = load_json_data(LINK_DATA_FILE, link_data_lock)
        self.user_data = current_user_data 
        self.link_data = current_link_data 

        active_links_to_check = []
        subscribed_urls = set()

        users_to_save = False

        for user_id_str, user_info_copy in list(current_user_data.items()): 
            user_info = current_user_data[user_id_str]
            if self._ensure_subscription_format_for_user(user_id_str, current_user_data):
                users_to_save = True

            if user_info.get("is_active", False):
                for sub_dict in user_info.get("subscriptions", []):
                    subscribed_urls.add(sub_dict["url"])
        
        if users_to_save:
            save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
            self.user_data = current_user_data 

        for url in subscribed_urls:
            link_info = current_link_data.get(url)
            if link_info and link_info.get("is_active", False):
                active_links_to_check.append({"normalized_url": url, "data": link_info})
        return active_links_to_check
        
    def update_link_check_status(self, normalized_url: str, error_increment: int = 0, success: bool = False):
        current_link_data = load_json_data(LINK_DATA_FILE, link_data_lock)
        if normalized_url in current_link_data:
            link = current_link_data[normalized_url]
            link["last_checked"] = self._get_current_utc_iso()
            if success:
                link["error_count"] = 0
            else:
                link["error_count"] = link.get("error_count", 0) + error_increment
            save_json_data(LINK_DATA_FILE, current_link_data, link_data_lock)
            self.link_data = current_link_data

    def deactivate_link(self, normalized_url: str):
        current_link_data = load_json_data(LINK_DATA_FILE, link_data_lock)
        if normalized_url in current_link_data:
            if current_link_data[normalized_url].get("is_active", True): 
                current_link_data[normalized_url]["is_active"] = False
                save_json_data(LINK_DATA_FILE, current_link_data, link_data_lock)
                self.link_data = current_link_data
                logger.warning(f"Link {normalized_url} deactivated.")

    # --- Методы для подписок ---
    def add_subscription(self, user_id: int, normalized_url: str) -> bool:
        user_id_str = str(user_id)
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)

        if user_id_str not in current_user_data:
            logger.error(f"Attempted to add subscription for non-existent user {user_id_str}")
            return False 
        
        user = current_user_data[user_id_str]
        needs_save = self._ensure_subscription_format_for_user(user_id_str, current_user_data)

        if not any(sub_dict["url"] == normalized_url for sub_dict in user.get("subscriptions", [])):
            user.setdefault("subscriptions", []).append({"url": normalized_url, "alias": None})
            needs_save = True
            logger.info(f"User {user_id_str} subscribed to {normalized_url}")
        else:
            logger.info(f"User {user_id_str} already subscribed to {normalized_url}")
            if needs_save:
                 save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
                 self.user_data = current_user_data
            return False 

        if needs_save:
            save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
            self.user_data = current_user_data
        return True

    def remove_subscription(self, user_id: int, normalized_url: str) -> bool:
        user_id_str = str(user_id)
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)
        
        if user_id_str not in current_user_data:
            return False
            
        user = current_user_data[user_id_str]
        needs_save = self._ensure_subscription_format_for_user(user_id_str, current_user_data)
        
        initial_len = len(user.get("subscriptions", []))
        user["subscriptions"] = [sub_dict for sub_dict in user.get("subscriptions", []) if sub_dict["url"] != normalized_url]
        
        if len(user["subscriptions"]) < initial_len:
            needs_save = True
            logger.info(f"User {user_id_str} unsubscribed from {normalized_url}")
        
        if needs_save:
            save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
            self.user_data = current_user_data
        
        return len(user["subscriptions"]) < initial_len

    def get_subscriptions_for_user(self, user_id: int) -> List[str]:
        user_id_str = str(user_id)
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)
        user = current_user_data.get(user_id_str)
        
        if user and user.get("is_active", False):
            if self._ensure_subscription_format_for_user(user_id_str, current_user_data):
                save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
                self.user_data = current_user_data 
            return user.get("subscriptions", [])
        return []
    
    def set_subscription_alias(self, user_id: int, normalized_url: str, alias: Optional[str]) -> bool:
        user_id_str = str(user_id)
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock)

        if user_id_str not in current_user_data:
            logger.warning(f"Cannot set alias for non-existent user {user_id_str}")
            return False

        user = current_user_data[user_id_str]
        needs_save = self._ensure_subscription_format_for_user(user_id_str, current_user_data)
        
        subscription_found = False
        for sub_dict in user.get("subscriptions", []):
            if sub_dict["url"] == normalized_url:
                if sub_dict.get("alias") != alias:
                    sub_dict["alias"] = alias
                    needs_save = True
                subscription_found = True
                break
        
        if not subscription_found:
            logger.warning(f"Subscription {normalized_url} not found for user {user_id_str} to set alias.")

            if needs_save:
                save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
                self.user_data = current_user_data
            return False

        if needs_save:
            save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
            self.user_data = current_user_data
            logger.info(f"Alias for {normalized_url} for user {user_id_str} set to '{alias}'.")
        return True

    def get_subscription_alias(self, user_id: int, normalized_url: str) -> Optional[str]:
        user_subscriptions = self.get_subscriptions_for_user(user_id)
        for sub_dict in user_subscriptions:
            if sub_dict["url"] == normalized_url:
                return sub_dict.get("alias")
        return None

    def get_active_subscribers_for_link(self, normalized_url: str) -> List[Dict[str, Any]]:

        subscribers = []
        current_user_data = load_json_data(USER_DATA_FILE, user_data_lock) 
        
        users_to_save_after_conversion = False
        for user_id_str, user_info_copy in list(current_user_data.items()):
            user_info = current_user_data[user_id_str] 
            if self._ensure_subscription_format_for_user(user_id_str, current_user_data):
                users_to_save_after_conversion = True

            if user_info.get("is_active", False):
                for sub_dict in user_info.get("subscriptions", []): 
                    if sub_dict["url"] == normalized_url:
                        subscribers.append({
                            "user_id": int(user_id_str),
                            "chat_id": user_info.get("chat_id")
                        })
                        break 
        
        if users_to_save_after_conversion:
            save_json_data(USER_DATA_FILE, current_user_data, user_data_lock)
            self.user_data = current_user_data 

        return subscribers

     # --- Методы для известных лотов (KnownLot) ---
    def add_lots_to_known(self, normalized_url: str, lots_data: List[Dict[str, str]]) -> int:
        added_count = 0
        current_link_data = load_json_data(LINK_DATA_FILE, link_data_lock)
        if normalized_url in current_link_data:
            link_entry = current_link_data[normalized_url]
            if "known_lot_guids" not in link_entry: 
                link_entry["known_lot_guids"] = []
            
            newly_added_guids_this_run = set() 
            for lot in lots_data:
                guid = lot.get('guid')
                if guid and guid not in link_entry["known_lot_guids"] and guid not in newly_added_guids_this_run:
                    link_entry["known_lot_guids"].append(guid)
                    newly_added_guids_this_run.add(guid)
                    added_count += 1
            
            if added_count > 0:
                save_json_data(LINK_DATA_FILE, current_link_data, link_data_lock)
                self.link_data = current_link_data
                logger.info(f"Added {added_count} new lot GUIDs to link {normalized_url}")
        return added_count

    def get_known_lot_guids_for_link(self, normalized_url: str) -> set:
        current_link_data = load_json_data(LINK_DATA_FILE, link_data_lock) 
        self.link_data = current_link_data
        link_entry = current_link_data.get(normalized_url)
        if link_entry and "known_lot_guids" in link_entry:
            return set(link_entry["known_lot_guids"])
        return set()