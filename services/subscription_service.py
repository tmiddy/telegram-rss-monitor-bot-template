import logging
from typing import List, Dict, Any, Tuple, Optional
from data_manager import DataManager

logger = logging.getLogger(__name__)

class SubscriptionService:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def add_user_subscription(self, user_id: int, normalized_url: str) -> bool:
        self.data_manager.get_or_create_link(normalized_url, normalized_url) 
        return self.data_manager.add_subscription(user_id, normalized_url)

    def remove_user_subscription(self, user_id: int, normalized_url: str) -> bool:
        return self.data_manager.remove_subscription(user_id, normalized_url)

    def get_user_subscriptions_display(self, user_id: int) -> List[Dict[str,str]]:
        user_subs_data = self.data_manager.get_subscriptions_for_user(user_id)
        display_subs = []
        for i, sub_info_dict in enumerate(user_subs_data):
            norm_url = sub_info_dict["url"]
            alias = sub_info_dict.get("alias") 

            link_data = self.data_manager.get_link(norm_url) 
            display_url = link_data.get('original_url_example', norm_url) if link_data else norm_url
            
            if link_data and link_data.get('is_active', True):
                 display_subs.append({
                     'index': i + 1, 
                     'normalized_url': norm_url, 
                     'display_url': display_url,
                     'alias': alias
                    })
        return display_subs
    
    def get_subscribers_for_link(self, normalized_url: str) -> List[Dict[str, Any]]:
        return self.data_manager.get_active_subscribers_for_link(normalized_url)

    def set_alias_for_subscription(
        self, 
        user_id: int, 
        subscription_identifier: str, 
        alias_name: Optional[str], 
        current_subscriptions_display: List[Dict[str, Any]] 
    ) -> Tuple[bool, Optional[str], Optional[str]]: 
        
        normalized_url_to_alias: Optional[str] = None
        display_url_of_aliased: Optional[str] = None

        if subscription_identifier.isdigit():
            try:
                index_to_find = int(subscription_identifier)
                found_sub = next((s for s in current_subscriptions_display if s['index'] == index_to_find), None)
                if found_sub:
                    normalized_url_to_alias = found_sub['normalized_url']
                    display_url_of_aliased = found_sub['display_url']
                else:
                    logger.warning(f"User {user_id}: Index {index_to_find} not found in their subscriptions.")
                    return False, None, None
            except ValueError: 
                logger.warning(f"User {user_id}: Invalid subscription index format {subscription_identifier}.")
                return False, None, None
        else: 

            found_sub_by_url = next((s for s in current_subscriptions_display if s['normalized_url'] == subscription_identifier or s['display_url'] == subscription_identifier), None)
            if found_sub_by_url:
                normalized_url_to_alias = found_sub_by_url['normalized_url']
                display_url_of_aliased = found_sub_by_url['display_url']
            else:

                logger.warning(f"User {user_id}: URL '{subscription_identifier}' not found directly in their subscriptions display.")
                return False, None, None

        if normalized_url_to_alias:
            success = self.data_manager.set_subscription_alias(user_id, normalized_url_to_alias, alias_name)
            if success:
                return True, normalized_url_to_alias, display_url_of_aliased
            else:
                logger.error(f"User {user_id}: Failed to set alias for {normalized_url_to_alias} in DataManager.")
                return False, normalized_url_to_alias, display_url_of_aliased
        
        logger.warning(f"User {user_id}: Could not determine subscription for alias operation with identifier '{subscription_identifier}'.")
        return False, None, None