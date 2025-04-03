import os
from pathlib import Path
import json
import logging
from .models import MediaCache as MediaCacheModel  # Нужно добавить модель

logger = logging.getLogger(__name__)

class MediaCache:
    def __init__(self):
        self.cache_file = Path('data/media_cache.json')
        self.cache = self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load media cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        self.cache_file.parent.mkdir(exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    async def get_media_id(self, file_path: str, bot) -> str:
        """Get file_id from cache or upload new file"""
        async with AsyncSessionFactory() as session:
            cached = await session.execute(
                select(MediaCacheModel)
                .where(MediaCacheModel.file_path == file_path)
            )
        abs_path = Path(file_path)
        
        if not abs_path.exists():
            logger.error(f"Media file not found: {file_path}")
            return None

        # Check if we have valid cached file_id
        if file_path in self.cache:
            try:
                # Verify file_id is still valid
                await bot.get_file(self.cache[file_path])
                logger.debug(f"Using cached file_id for {file_path}")
                return self.cache[file_path]
            except Exception as e:
                logger.warning(f"Cached file_id invalid for {file_path}: {e}")
                del self.cache[file_path]

        # Upload new file and cache file_id
        try:
            if file_path.endswith(('.jpg', '.jpeg', '.png')):
                result = await bot.send_photo(
                    chat_id=ADMIN_GROUP_ID,
                    photo=FSInputFile(file_path),
                    disable_notification=True
                )
                file_id = result.photo[-1].file_id
            elif file_path.endswith(('.mp4', '.mov')):
                result = await bot.send_video(
                    chat_id=ADMIN_GROUP_ID,
                    video=FSInputFile(file_path),
                    disable_notification=True
                )
                file_id = result.video.file_id

            logger.info(f"New file uploaded and cached: {file_path}")
            self.cache[file_path] = file_id
            self._save_cache()
            return file_id

        except Exception as e:
            logger.error(f"Failed to upload media {file_path}: {e}")
            return None

media_cache = MediaCache()