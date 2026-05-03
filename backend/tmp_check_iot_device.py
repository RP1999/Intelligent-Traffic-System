import json

import boto3
from boto3.dynamodb.conditions import Key

from app.config import get_settings


def main() -> None:
    s = get_settings()
    session_kwargs = {}
    if s.aws_access_key_id and s.aws_secret_access_key:
        session_kwargs["aws_access_key_id"] = s.aws_access_key_id
        session_kwargs["aws_secret_access_key"] = s.aws_secret_access_key
    if s.aws_session_token:
        session_kwargs["aws_session_token"] = s.aws_session_token

    session = boto3.session.Session(**session_kwargs)
    table = session.resource("dynamodb", region_name=s.aws_region).Table(s.iot_dynamodb_table)

    resp_exact = table.query(
        KeyConditionExpression=Key(s.iot_dynamodb_junction_key).eq(s.iot_dynamodb_junction_id),
        ScanIndexForward=False,
        Limit=1,
    )

    scan = table.scan(Limit=300)
    items = scan.get("Items", [])
    items.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)
    latest = items[0] if items else {}

    print(
        json.dumps(
            {
                "configured_device_id": s.iot_dynamodb_junction_id,
                "exact_query_item_count": len(resp_exact.get("Items", [])),
                "latest_table_device_id": str(latest.get("deviceId", "")),
                "latest_table_timestamp": int(latest.get("timestamp", 0)) if latest else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
