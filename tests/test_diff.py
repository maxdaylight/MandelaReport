from src.core.diff import diff_texts_html


def test_diff_texts_html_basic():
    a = "The quick brown fox jumps over the lazy dog"
    b = "The quick brown fox leaps over the lazy dog"
    html = diff_texts_html(a, b)
    assert "diff-ins" in html or "diff-del" in html


def test_diff_texts_html_insert_and_delete():
    a = "Hello world"
    b = "Hello brave new world"
    html = diff_texts_html(a, b)
    assert "brave" in html
    assert "new" in html
    assert "diff-ins" in html
