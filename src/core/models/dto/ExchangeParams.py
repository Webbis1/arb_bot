from typing import Any, NotRequired, TypedDict


class ExchangeParams(TypedDict, total=False):
    apiKey: str
    secret: str
    sandbox: NotRequired[bool]
    enableRateLimit: NotRequired[bool]
    timeout: NotRequired[int]
    verify: NotRequired[bool]
    # Дополнительные параметры, которые могут быть в ex_config
    password: NotRequired[str]
    uid: NotRequired[str]
    # Любые другие параметры, специфичные для биржи
    options: NotRequired[dict[str, Any]]
    
    
DEFAULT_PARAMS: ExchangeParams = {
    "sandbox": False,
    "enableRateLimit": True,
    "timeout": 30000,
    "verify": True,
    "options": {}
}