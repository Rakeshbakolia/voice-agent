from catalog.chat_tools import execute_tool_call


def test_execute_unknown_tool() -> None:
    assert "Unknown tool" in execute_tool_call("not_a_tool", "{}")
