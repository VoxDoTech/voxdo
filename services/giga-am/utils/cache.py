"""
Система кэширования результатов распознавания
"""
import hashlib
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Запись в кэше"""
    result: Dict[str, Any]
    file_hash: str
    audio_metadata: Dict[str, Any]
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def age_seconds(self) -> float:
        """Возраст записи в секундах"""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()
    
    @property
    def is_expired(self) -> bool:
        """Проверка истечения срока хранения"""
        from config import settings
        max_age_hours = settings.cache_max_age_hours
        return self.age_seconds > (max_age_hours * 3600)


from config import settings


class TranscriptionCache:
    """Кэш результатов распознавания"""
    
    def __init__(self, max_size: int = None, max_age_hours: int = None):
        self.max_size = max_size or settings.cache_max_size
        self.max_age_hours = max_age_hours or settings.cache_max_age_hours
        self._lock = threading.RLock()
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_requests": 0
        }
    
    def _generate_cache_key(self, file_hash: str, pipeline_config: Dict[str, Any]) -> str:
        """Генерация ключа кэша"""
        # Создаем строку конфигурации pipeline
        config_str = json.dumps(pipeline_config, sort_keys=True, separators=(',', ':'))
        
        # Генерируем хеш из file_hash и конфигурации
        key_data = f"{file_hash}:{config_str}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get_pipeline_config(self) -> Dict[str, Any]:
        """
        Получение текущей конфигурации pipeline.
        
        Включены только те параметры, которые влияют на результат Python сервиса.
        LLM коррекция выполняется в Inngest и не влияет на кэш этого сервиса.
        """
        from config import settings

        return {
            "model_name": settings.model_name,
            "max_file_size": settings.max_file_size,
        }
    
    def get(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Получение результата из кэша"""
        with self._lock:
            self._stats["total_requests"] += 1
            
            pipeline_config = self.get_pipeline_config()
            cache_key = self._generate_cache_key(file_hash, pipeline_config)
            
            if cache_key not in self._cache:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss for key: {cache_key[:16]}...")
                return None
            
            entry = self._cache[cache_key]
            
            # Проверка истечения срока
            if entry.is_expired:
                logger.debug(f"Cache entry expired for key: {cache_key[:16]}...")
                del self._cache[cache_key]
                self._stats["misses"] += 1
                return None
            
            # Обновление статистики доступа
            entry.access_count += 1
            entry.last_accessed = datetime.now(timezone.utc)
            
            self._stats["hits"] += 1
            logger.debug(f"Cache hit for key: {cache_key[:16]}... (access #{entry.access_count})")
            
            # Возвращаем копию результата для безопасности
            return json.loads(json.dumps(entry.result))
    
    def put(self, file_hash: str, result: Dict[str, Any], audio_metadata: Dict[str, Any]):
        """Сохранение результата в кэш"""
        with self._lock:
            pipeline_config = self.get_pipeline_config()
            cache_key = self._generate_cache_key(file_hash, pipeline_config)
            
            # Проверка размера кэша
            if len(self._cache) >= self.max_size:
                self._evict_lru()
            
            # Создание новой записи
            entry = CacheEntry(
                result=json.loads(json.dumps(result)),  # Глубокая копия
                file_hash=file_hash,
                audio_metadata=json.loads(json.dumps(audio_metadata)),
                created_at=datetime.now(timezone.utc)
            )
            
            self._cache[cache_key] = entry
            logger.debug(f"Cached result for key: {cache_key[:16]}...")
    
    def _evict_lru(self):
        """Удаление наименее используемых записей"""
        if not self._cache:
            return
        
        # Сортировка по времени последнего доступа
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Удаляем 10% самых старых записей
        evict_count = max(1, len(sorted_entries) // 10)
        
        for i in range(evict_count):
            key = sorted_entries[i][0]
            del self._cache[key]
            self._stats["evictions"] += 1
        
        logger.debug(f"Evicted {evict_count} entries from cache")
    
    def clear_expired(self):
        """Очистка истекших записей"""
        with self._lock:
            expired_keys = []
            current_time = datetime.now(timezone.utc)
            
            for key, entry in self._cache.items():
                if (current_time - entry.created_at).total_seconds() > (self.max_age_hours * 3600):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                self._stats["evictions"] += 1
            
            if expired_keys:
                logger.debug(f"Cleared {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        with self._lock:
            total_requests = self._stats["total_requests"]
            hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
            
            # Анализ размера записей
            entries_by_age = {"0-1h": 0, "1-6h": 0, "6-24h": 0, "24h+": 0}
            current_time = datetime.now(timezone.utc)
            
            for entry in self._cache.values():
                age_hours = entry.age_seconds / 3600
                if age_hours <= 1:
                    entries_by_age["0-1h"] += 1
                elif age_hours <= 6:
                    entries_by_age["1-6h"] += 1
                elif age_hours <= 24:
                    entries_by_age["6-24h"] += 1
                else:
                    entries_by_age["24h+"] += 1
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": round(hit_rate, 2),
                "stats": self._stats.copy(),
                "entries_by_age": entries_by_age,
                "memory_usage_mb": self._estimate_memory_usage()
            }
    
    def _estimate_memory_usage(self) -> float:
        """Оценка использования памяти в МБ"""
        try:
            total_size = 0
            for entry in self._cache.values():
                # Приблизительная оценка размера JSON данных
                result_size = len(json.dumps(entry.result).encode())
                metadata_size = len(json.dumps(entry.audio_metadata).encode())
                total_size += result_size + metadata_size
            
            return round(total_size / (1024 * 1024), 2)
        except Exception:
            return 0.0
    
    def cleanup(self):
        """Полная очистка кэша"""
        with self._lock:
            cache_size = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {cache_size} entries removed")


# Глобальный экземпляр кэша
cache = TranscriptionCache()


def setup_cache_cleanup():
    """Настройка периодической очистки кэша"""
    def cleanup_worker():
        while True:
            try:
                time.sleep(3600)  # Каждый час
                cache.clear_expired()
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    thread = threading.Thread(target=cleanup_worker, daemon=True)
    thread.start()
    logger.info("Cache cleanup worker started")
