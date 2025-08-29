import difflib
import html


def _split_words(text: str):
    return text.split()


def diff_texts_html(a: str, b: str) -> str:
    a_words = _split_words(a)
    b_words = _split_words(b)
    sm = difflib.SequenceMatcher(a=a_words, b=b_words)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            seg = " ".join(html.escape(w) for w in b_words[j1:j2])
            out.append(seg)
        elif tag == "insert":
            seg = " ".join(html.escape(w) for w in b_words[j1:j2])
            out.append(f'<ins class="diff-ins">{seg}</ins>')
        elif tag == "delete":
            seg = " ".join(html.escape(w) for w in a_words[i1:i2])
            out.append(f'<del class="diff-del">{seg}</del>')
        elif tag == "replace":
            del_seg = " ".join(html.escape(w) for w in a_words[i1:i2])
            ins_seg = " ".join(html.escape(w) for w in b_words[j1:j2])
            out.append(
                f'<del class="diff-del">{del_seg}</del>'
                f'<ins class="diff-ins">{ins_seg}</ins>'
            )
    return '<div class="diff-body">' + " ".join(out) + "</div>"


def diff_change_ratio(a: str, b: str) -> dict:
    """Compute basic change statistics between two texts.

    Returns a dict with:
    - total_tokens: int
    - changed_tokens: int
    - ratio: float in [0,1]
    """
    a_words = _split_words(a)
    b_words = _split_words(b)
    sm = difflib.SequenceMatcher(a=a_words, b=b_words)
    changed = 0
    total = max(len(a_words), len(b_words)) or 1
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        # count replaced/deleted/inserted as changed based on b-side span
        changed += max(j2 - j1, i2 - i1)
    ratio = min(1.0, max(0.0, changed / total))
    return {"total_tokens": total, "changed_tokens": changed, "ratio": ratio}
