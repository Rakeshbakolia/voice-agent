from call_context import CallContext, build_agent_instructions


def test_instructions_mention_catalog_tools() -> None:
    call = CallContext(
        contact_name="Alex",
        company_name="Game Guide",
        company_summary="Helps pick games.",
    )
    text = build_agent_instructions(call)
    assert "search_games" in text
    assert "search_similar_games" in text
    assert "Never invent game titles" in text
