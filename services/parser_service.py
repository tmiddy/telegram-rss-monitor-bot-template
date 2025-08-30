
import feedparser
import logging
import re
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)




class ParserService:
    def parse_rss_feed(self, feed_content: bytes) -> Optional[List[Dict[str, str]]]:
        lots_data = []
        try:
            feed = feedparser.parse(feed_content)
            if feed.bozo:
                logger.warning(f"Feed parsing resulted in bozo: {feed.bozo_exception}")
            
            for entry in feed.entries:
                guid = entry.get('guid') or entry.get('id') or entry.get('link')
                title = entry.get('title', 'N/A')
                link = entry.get('link')
                description = entry.get('description', '')

                if not guid:
                    logger.warning(f"Skipping entry, no GUID found. Title: {title[:50]}...")
                    continue
                
                lots_data.append({
                    'guid': guid,
                    'title': title,
                    'url': link or guid,
                    'description': description
                })
            logger.info(f"Parsed {len(lots_data)} entries from feed.")
            return lots_data
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}", exc_info=True)
            return None
