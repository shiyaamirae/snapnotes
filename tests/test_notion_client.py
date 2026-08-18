from snapnotes.notion_client import build_bullets_children, build_table_children, extract_page_id


def test_extract_page_id_from_full_url():
    url = "https://www.notion.so/My-Page-abc123def4567890abc123def4567890"
    assert extract_page_id(url) == "abc123def4567890abc123def4567890"


def test_extract_page_id_passes_through_bare_id():
    assert extract_page_id("abc123def4567890abc123def4567890") == "abc123def4567890abc123def4567890"


def test_extract_page_id_strips_query_string():
    url = "https://www.notion.so/My-Page-abc123def4567890abc123def4567890?pvs=4"
    assert extract_page_id(url) == "abc123def4567890abc123def4567890"


def test_table_children_shape():
    children = build_table_children("Title", ["A", "B"], [["1", "2"], ["3", "4"]])
    table = children[1]
    assert table["type"] == "table"
    assert table["table"]["table_width"] == 2
    # header row + 2 data rows
    assert len(table["table"]["children"]) == 3


def test_bullets_children_shape():
    children = build_bullets_children("Title", ["one", "two", "three"])
    bullet_blocks = [c for c in children if c["type"] == "bulleted_list_item"]
    assert len(bullet_blocks) == 3


def test_both_end_with_divider():
    assert build_table_children("T", ["A"], [["1"]])[-1]["type"] == "divider"
    assert build_bullets_children("T", ["a"])[-1]["type"] == "divider"
