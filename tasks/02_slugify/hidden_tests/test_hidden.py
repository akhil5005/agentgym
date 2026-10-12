from src.text import slugify


def test_result_is_lowercase():
    assert slugify("LOUD TITLE") == "loud-title"


def test_runs_of_spaces_collapse_to_one_hyphen():
    assert slugify("a      b") == "a-b"


def test_runs_of_punctuation_collapse_to_one_hyphen():
    assert slugify("what?!... now") == "what-now"


def test_no_leading_hyphen():
    assert slugify("!!!leading") == "leading"


def test_no_trailing_hyphen():
    assert slugify("trailing???") == "trailing"


def test_accents_become_plain_ascii():
    assert slugify("Café") == "cafe"


def test_several_accented_words():
    assert slugify("Crème Brûlée") == "creme-brulee"


def test_underscores_become_hyphens():
    assert slugify("snake_case_name") == "snake-case-name"


def test_digits_are_kept():
    assert slugify("Top 10 Albums of 1999") == "top-10-albums-of-1999"


def test_empty_string():
    assert slugify("") == ""


def test_text_with_no_letters_or_digits():
    assert slugify("!!! ??? ...") == ""
