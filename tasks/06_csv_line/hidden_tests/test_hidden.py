from src.csvline import parse_csv_line


def test_plain_fields():
    assert parse_csv_line("a,b,c") == ["a", "b", "c"]


def test_single_field_with_no_commas():
    assert parse_csv_line("single") == ["single"]


def test_empty_line_is_one_empty_field():
    assert parse_csv_line("") == [""]


def test_empty_fields_in_the_middle():
    assert parse_csv_line("a,,b") == ["a", "", "b"]


def test_comma_inside_quotes_is_kept():
    assert parse_csv_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_empty_quoted_field():
    assert parse_csv_line('a,"",b') == ["a", "", "b"]


def test_spaces_inside_quotes_are_preserved():
    assert parse_csv_line('"  pad ""ded""  ",x') == ['  pad "ded"  ', "x"]


def test_trailing_comma_gives_an_empty_last_field():
    assert parse_csv_line('"a""b",') == ['a"b', ""]


def test_doubled_quotes_become_one_quote():
    assert parse_csv_line('"say ""hi"""') == ['say "hi"']


def test_doubled_quotes_with_no_surrounding_text():
    assert parse_csv_line('"a""b"') == ['a"b']


def test_whole_field_wrapped_in_literal_quotes():
    assert parse_csv_line('"""quoted"""') == ['"quoted"']


def test_doubled_quote_followed_by_a_comma_inside_quotes():
    assert parse_csv_line('"a"",b"') == ['a",b']
