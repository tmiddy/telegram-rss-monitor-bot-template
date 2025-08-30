
import logging
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional, Dict
from data_manager import DataManager 

logger = logging.getLogger(__name__)

class LinkService:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def normalize_url(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url.strip())
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Invalid URL structure for normalization: {url}")
                return None
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            query_params = parse_qs(parsed.query)
            sorted_query = urlencode(sorted(query_params.items()), doseq=True)
            normalized = urlunparse((scheme, netloc, parsed.path, parsed.params, sorted_query, ''))
            logger.debug(f"Normalized URL: {url} -> {normalized}")
            return normalized
        except Exception as e:
            logger.error(f"Error normalizing URL {url}: {e}")
            return None

    def add_new_link(self, normalized_url: str, original_url: str) -> Dict:
        return self.data_manager.get_or_create_link(normalized_url, original_url)

    def get_link_data(self, normalized_url: str) -> Optional[Dict]:
        return self.data_manager.get_link(normalized_url)
    
    def deactivate_link_due_to_errors(self, normalized_url: str, max_errors: int) -> bool:
        link_data = self.data_manager.get_link(normalized_url) 
        if link_data and link_data.get('is_active', True) and link_data.get('error_count', 0) >= max_errors :
            self.data_manager.deactivate_link(normalized_url)
            logger.warning(f"Link {normalized_url} deactivated after {link_data.get('error_count', 0)} errors.")
            return True
        return False