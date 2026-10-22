from app.describe import batches, parse


def test_parse_description():
    page = """<div class="object_card_discr">
\t\t\t<span>Классический глубокий чайный вкус
с ярким бергамотом &amp; цедрой.<br>Вторая строка.</span>
\t\t</div>"""
    assert parse(page) == "Классический глубокий чайный вкус с ярким бергамотом & цедрой.\nВторая строка."


def test_parse_missing():
    assert parse("<div class='other'></div>") == ""


def test_batches_by_encoded_size():
    texts = {i: "вкус " * 20 for i in range(10)}  # ~600 bytes each once encoded
    runs = batches(list(texts), texts.get, limit=2000)
    assert [k for run in runs for k in run] == list(texts)
    assert all(len(run) <= 3 for run in runs) and len(runs) >= 4
