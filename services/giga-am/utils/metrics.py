"""
Система метрик и мониторинга для GigaAM API
"""
import time
import psutil
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


from config import settings


@dataclass
class RequestMetrics:
    """Метрики для одного запроса"""
    start_time: float
    end_time: Optional[float] = None
    file_size: int = 0
    file_hash: str = ""
    audio_duration: float = 0.0
    success: bool = False
    error_code: Optional[str] = None
    stages: List[str] = field(default_factory=list)
    stage_times: Dict[str, float] = field(default_factory=dict)
    result_retrieval: bool = False
    
    @property
    def duration(self) -> float:
        """Длительность обработки запроса"""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def processing_rate(self) -> float:
        """Скорость обработки (секунды аудио в секунду обработки)"""
        if self.duration > 0 and self.audio_duration > 0:
            return self.audio_duration / self.duration
        return 0.0


class MetricsCollector:
    """Коллектор метрик производительности"""
    
    def __init__(self, max_history_size: int = None):
        self.max_history_size = max_history_size or settings.metrics_history_size
        self._lock = threading.RLock()
        
        # История запросов
        self.request_history: deque = deque(maxlen=self.max_history_size)
        
        # Счетчики
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # Агрегированные метрики
        self.stage_metrics: Dict[str, List[float]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        
        # Текущая нагрузка
        self.active_requests: Dict[str, RequestMetrics] = {}
        
        # Системные метрики
        self._system_metrics_history: deque = deque(maxlen=100)

        # Счетчик обращений за результатами
        self.result_retrievals = 0
        
        # Запуск фонового сбора системных метрик
        self._start_system_metrics_collection()
    
    def start_request(self, request_id: str, file_size: int = 0, file_hash: str = "") -> RequestMetrics:
        """Начало отслеживания запроса"""
        with self._lock:
            metrics = RequestMetrics(
                start_time=time.time(),
                file_size=file_size,
                file_hash=file_hash
            )
            
            self.active_requests[request_id] = metrics
            self.total_requests += 1
            
            logger.debug(f"Начало отслеживания запроса {request_id}")
            return metrics
    
    def end_request(self, request_id: str, success: bool = True, error_code: Optional[str] = None):
        """Завершение отслеживания запроса"""
        with self._lock:
            if request_id not in self.active_requests:
                logger.warning(f"Запрос {request_id} не найден в активных")
                return
            
            metrics = self.active_requests[request_id]
            metrics.end_time = time.time()
            metrics.success = success
            metrics.error_code = error_code
            
            # Обновляем счетчики
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                if error_code:
                    self.error_counts[error_code] += 1
            
            # Перемещаем в историю
            self.request_history.append(metrics)
            del self.active_requests[request_id]
            
            logger.debug(f"Завершение отслеживания запроса {request_id}: {metrics.duration:.2f}s")
    
    def record_stage_time(self, request_id: str, stage: str, duration: float):
        """Запись времени выполнения этапа"""
        with self._lock:
            if request_id in self.active_requests:
                metrics = self.active_requests[request_id]
                metrics.stages.append(stage)
                metrics.stage_times[stage] = duration
                self.stage_metrics[stage].append(duration)
    
    def set_audio_duration(self, request_id: str, duration: float):
        """Установка длительности аудио"""
        with self._lock:
            if request_id in self.active_requests:
                self.active_requests[request_id].audio_duration = duration
    
    def record_result_retrieval(self, request_id: str) -> None:
        """Запрос результатов из хранилища"""
        with self._lock:
            self.result_retrievals += 1
            if request_id in self.active_requests:
                self.active_requests[request_id].result_retrieval = True
        logger.info(f"Result retrieval recorded for request: {request_id}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Получение текущей статистики"""
        with self._lock:
            # Базовые метрики
            success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
            
            # Метрики производительности
            recent_requests = list(self.request_history)[-100:]  # Последние 100 запросов
            avg_duration = sum(r.duration for r in recent_requests) / len(recent_requests) if recent_requests else 0
            
            # Исправляем деление на ноль для avg_processing_rate
            positive_rates = [r.processing_rate for r in recent_requests if r.processing_rate > 0]
            avg_processing_rate = sum(positive_rates) / len(positive_rates) if positive_rates else 0
            
            # Метрики по этапам
            stage_stats = {}
            for stage, times in list(self.stage_metrics.items())[-50:]:  # Последние 50 измерений
                if times:
                    stage_stats[stage] = {
                        "avg": sum(times) / len(times),
                        "min": min(times),
                        "max": max(times),
                        "count": len(times)
                    }
            
            # Системные метрики
            system_stats = self._get_system_metrics()
            
            return {
                "requests": {
                    "total": self.total_requests,
                    "successful": self.successful_requests,
                    "failed": self.failed_requests,
                    "active": len(self.active_requests),
                    "success_rate": round(success_rate, 2)
                },
                "performance": {
                    "avg_duration": round(avg_duration, 3),
                    "avg_processing_rate": round(avg_processing_rate, 3),
                    "recent_requests_count": len(recent_requests)
                },
                "stages": stage_stats,
                "errors": dict(self.error_counts),
                "system": system_stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Получение системных метрик"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Память
            memory = psutil.virtual_memory()
            
            # Диск
            disk = psutil.disk_usage('/')
            
            # Сеть
            network = psutil.net_io_counters()
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                }
            }
        except Exception as e:
            logger.warning(f"Ошибка при получении системных метрик: {e}")
            return {}
    
    def _start_system_metrics_collection(self):
        """Запуск фонового сбора системных метрик"""
        def collect_system_metrics():
            while True:
                try:
                    metrics = self._get_system_metrics()
                    if metrics:
                        self._system_metrics_history.append({
                            "timestamp": time.time(),
                            "metrics": metrics
                        })
                    time.sleep(settings.system_metrics_interval)  # Используем настройку из config
                except Exception as e:
                    logger.error(f"Ошибка в фоновом сборе метрик: {e}")
                    time.sleep(60)  # При ошибке ждем дольше
        
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
        logger.info("Фоновый сбор системных метрик запущен")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получение статуса здоровья сервиса"""
        with self._lock:
            # Проверяем нагрузку
            system_metrics = self._get_system_metrics()
            
            # Критерии здоровья
            health_issues = []
            
            # CPU нагрузка
            if system_metrics.get("cpu", {}).get("percent", 0) > 90:
                health_issues.append("Высокая загрузка CPU")
            
            # Память
            if system_metrics.get("memory", {}).get("percent", 0) > 90:
                health_issues.append("Высокое использование памяти")
            
            # Диск
            if system_metrics.get("disk", {}).get("percent", 0) > 95:
                health_issues.append("Мало места на диске")
            
            # Успешность запросов
            if self.total_requests > 10:  # Проверяем только если было достаточно запросов
                recent_success_rate = (self.successful_requests / self.total_requests * 100)
                if recent_success_rate < 90:
                    health_issues.append("Низкий процент успешных запросов")
            
            # Активные запросы
            if len(self.active_requests) > 10:  # Слишком много активных запросов
                health_issues.append("Слишком много активных запросов")
            
            status = "healthy" if not health_issues else "degraded" if len(health_issues) <= 2 else "unhealthy"
            
            return {
                "status": status,
                "issues": health_issues,
                "active_requests": len(self.active_requests),
                "recent_success_rate": round((self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0, 2),
                "system_load": {
                    "cpu": system_metrics.get("cpu", {}).get("percent", 0),
                    "memory": system_metrics.get("memory", {}).get("percent", 0),
                    "disk": system_metrics.get("disk", {}).get("percent", 0)
                }
            }


# Глобальный экземпляр коллектора метрик
metrics = MetricsCollector()


class RequestTracker:
    """Контекст менеджер для отслеживания запросов"""
    
    def __init__(self, request_id: str, file_size: int = 0, file_hash: str = ""):
        self.request_id = request_id
        self.file_size = file_size
        self.file_hash = file_hash
        self.metrics: Optional[RequestMetrics] = None
    
    def __enter__(self) -> RequestMetrics:
        self.metrics = metrics.start_request(self.request_id, self.file_size, self.file_hash)
        return self.metrics
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        error_code = exc_val.error_code if hasattr(exc_val, 'error_code') else str(exc_val) if exc_val else None
        metrics.end_request(self.request_id, success, error_code)
