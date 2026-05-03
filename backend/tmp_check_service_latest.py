import asyncio
import json
from decimal import Decimal
from datetime import datetime

from app.services.iot_junction_service import get_iot_junction_service


def to_native(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_native(v) for v in value]
    return value


async def main() -> None:
    service = get_iot_junction_service()
    status = await service.get_latest_status(force_refresh=True)
    print(json.dumps(to_native(status), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
