"""Parsing a single line of CSV."""


def parse_csv_line(line):
    """Split one CSV line into its fields."""
    fields = []
    current = []
    in_quotes = False

    # An index loop rather than `for char in line`, because recognising a
    # doubled quote means looking at the next character and then skipping it.
    index = 0
    while index < len(line):
        char = line[index]

        if char == '"':
            # Inside a quoted field, "" is an escaped quote, not the end of the
            # field followed by the start of another one.
            if in_quotes and index + 1 < len(line) and line[index + 1] == '"':
                current.append('"')
                index += 2
                continue
            in_quotes = not in_quotes
            index += 1
            continue

        if char == "," and not in_quotes:
            fields.append("".join(current))
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    fields.append("".join(current))
    return fields
