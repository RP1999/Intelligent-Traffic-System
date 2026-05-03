from app.config import get_settings
import boto3

s = get_settings()

session_kwargs = {}
if s.aws_access_key_id and s.aws_secret_access_key:
    session_kwargs["aws_access_key_id"] = s.aws_access_key_id
    session_kwargs["aws_secret_access_key"] = s.aws_secret_access_key
if s.aws_session_token:
    session_kwargs["aws_session_token"] = s.aws_session_token

session = boto3.session.Session(**session_kwargs)
table = session.resource("dynamodb", region_name=s.aws_region).Table(s.iot_dynamodb_table)

res = table.get_item(
    Key={
        s.iot_dynamodb_junction_key: s.iot_dynamodb_junction_id,
        s.iot_dynamodb_sort_key: 19260,
    }
)
item = res.get("Item")
print("exists:", bool(item))
if item:
    print("timestamp:", item.get("timestamp"))
    print("created_at:", item.get("created_at"))
    print("lane1:", item.get("lane1"), "lane2:", item.get("lane2"), "lane3:", item.get("lane3"), "emergency:", item.get("emergency"))
