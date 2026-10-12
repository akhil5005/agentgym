"""Parsing a single line of CSV."""


def parse_csv_line(line):
    """Split one CSV line into its fields."""
    fields = []
    current = []
    in_quotes = False

    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            fields.append("".join(current))
            current = []
        else:
            current.append(char)

    fields.append("".join(current))
    return fields
