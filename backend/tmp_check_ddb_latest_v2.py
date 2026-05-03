from app.config import get_settings
import boto3
from boto3.dynamodb.conditions import Key

s = get_settings()

session_kwargs = {}
if s.aws_access_key_id and s.aws_secret_access_key:
    session_kwargs["aws_access_key_id"] = s.aws_access_key_id
    session_kwargs["aws_secret_access_key"] = s.aws_secret_access_key
if s.aws_session_token:
    session_kwargs["aws_session_token"] = s.aws_session_token

session = boto3.session.Session(**session_kwargs)
table = session.resource("dynamodb", region_name=s.aws_region).Table(s.iot_dynamodb_table)

res = table.query(
    KeyConditionExpression=Key(s.iot_dynamodb_junction_key).eq(s.iot_dynamodb_junction_id),
    ScanIndexForward=False,
    Limit=10,
)
items = res.get("Items", [])

print("deviceId:", s.iot_dynamodb_junction_id)
print("count_returned:", len(items))
for i, it in enumerate(items, 1):
    print(
        f"#{i}",
        "timestamp=", it.get("timestamp"),
        "created_at=", it.get("created_at"),
        "lane1=", it.get("lane1"),
        "lane2=", it.get("lane2"),
        "lane3=", it.get("lane3"),
        "emergency=", it.get("emergency"),
    )
