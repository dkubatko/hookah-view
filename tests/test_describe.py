from app.describe import parse


def test_parse_description():
    page = """<div class="object_card_discr">
\t\t\t<span>Классический глубокий чайный вкус
с ярким бергамотом &amp; цедрой.<br>Вторая строка.</span>
\t\t</div>"""
    assert parse(page) == "Классический глубокий чайный вкус с ярким бергамотом & цедрой.\nВторая строка."


def test_parse_missing():
    assert parse("<div class='other'></div>") == ""
