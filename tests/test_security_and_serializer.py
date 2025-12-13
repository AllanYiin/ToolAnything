from toolanything.core.result_serializer import ResultSerializer
from toolanything.core.security_manager import SecurityManager


def test_security_manager_masks_keys_and_audit():
    manager = SecurityManager()
    record = {"apiKey": "secret", "username": "alice", "nestedKey": "value"}

    masked = manager.mask_keys_in_log(record)

    assert masked["apiKey"] == "***MASKED***"
    assert masked["nestedKey"] == "***MASKED***"
    assert masked["username"] == "alice"

    audit = manager.audit_call("demo.tool", record, user="bob")
    assert audit == {"tool": "demo.tool", "user": "bob", "args": masked}


def test_result_serializer_outputs():
    serializer = ResultSerializer()

    assert serializer.to_openai({"a": 1}) == {"type": "json", "content": {"a": 1}}
    assert serializer.to_openai([1, 2]) == {"type": "json", "content": [1, 2]}
    assert serializer.to_openai("text") == {"type": "text", "content": "text"}

    assert serializer.to_mcp({"a": 1}) == {"contentType": "application/json", "content": {"a": 1}}
    assert serializer.to_mcp((1, 2)) == {"contentType": "application/json", "content": [1, 2]}
    assert serializer.to_mcp(True) == {"contentType": "text/plain", "content": "True"}
