from typing import Literal, NotRequired, TypedDict


class DepositAddressResponse(TypedDict):
    """Полный ответ с депозитным адресом"""
    # Обязательные поля
    address: str
    coin: str
    
    # Опциональные поля
    tag: NotRequired[str]
    memo: NotRequired[str]
    url: NotRequired[str]
    network: NotRequired[str]
    chain: NotRequired[str]
    
    # Дополнительная информация
    status: NotRequired[Literal['active', 'inactive', 'pending']]
    message: NotRequired[str]
    timestamp: NotRequired[float]
    
    # Для некоторых бирж
    destination: NotRequired[str]  # Альтернатива address
    payment_id: NotRequired[str]   # Для Monero и подобных
