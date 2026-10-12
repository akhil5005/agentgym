from src.csvline import parse_csv_line


def test_plain_fields():
    assert parse_csv_line("a,b,c") == ["a", "b", "c"]


def test_comma_inside_quotes_is_not_a_separator():
    assert parse_csv_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_doubled_quotes_become_one_quote():
    assert parse_csv_line('"say ""hi"""') == ['say "hi"']


def test_doubled_quotes_in_the_middle_of_a_row():
    assert parse_csv_line('x,"a""b",y') == ["x", 'a"b', "y"]
