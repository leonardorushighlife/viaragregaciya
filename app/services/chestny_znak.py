from abc import ABC, abstractmethod
from typing import List, Dict, Any
import uuid

class AbstractChestnyZnakService(ABC):
    @abstractmethod
    async def request_marking_codes(self, gtin: str, quantity: int) -> Dict[str, Any]:
        """Заказ кодов маркировки"""
        pass

    @abstractmethod
    async def get_order_status(self, cz_order_id: str) -> Dict[str, Any]:
        """Проверка статуса заказа кодов"""
        pass

class MockChestnyZnakService(AbstractChestnyZnakService):
    async def request_marking_codes(self, gtin: str, quantity: int) -> Dict[str, Any]:
        mock_order_id = f"cz_order_{uuid.uuid4().hex[:8]}"
        codes = [f"01{gtin or '00000000000000'}21{uuid.uuid4().hex[:13]}" for _ in range(min(quantity, 100))]
        return {
            "status": "SUCCESS",
            "cz_order_id": mock_order_id,
            "codes_count": quantity,
            "sample_codes": codes,
            "message": f"Успешно сгенерировано {quantity} тестовых кодов Честный Знак"
        }

    async def get_order_status(self, cz_order_id: str) -> Dict[str, Any]:
        return {
            "cz_order_id": cz_order_id,
            "status": "READY",
            "message": "Коды готовы к печати"
        }

cz_service = MockChestnyZnakService()
