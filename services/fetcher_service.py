
import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from config import USER_AGENT 
from typing import Optional

logger = logging.getLogger(__name__)

class FetcherService:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_url_content(self, url: str) -> Optional[bytes]:
        try:
            logger.debug(f"Fetching URL: {url}")
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            logger.info(f"Successfully fetched {url}, status: {response.status_code}")
            return response.content
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error fetching {url}: {e.response.status_code} {e.response.reason}")
            if 400 <= e.response.status_code < 500 and e.response.status_code not in [408, 429]:
                raise 
            raise 
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception fetching {url}: {e}")
            raise 
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            raise