from catalog.embeddings import truncate_for_embed


def test_truncate_for_embed_short() -> None:
    assert truncate_for_embed("hello") == "hello"


def test_truncate_for_embed_long() -> None:
    text = "x" * 9000
    out = truncate_for_embed(text, max_chars=100)
    assert len(out) == 100
    assert out.endswith("...")
