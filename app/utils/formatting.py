def format_inr(amount: float) -> str:
    """Format a number using Indian number system (lakhs and crores).

    Examples:
        1234567    → ₹12,34,567
        100000     → ₹1,00,000
        12345678   → ₹1,23,45,678
    """
    is_negative = amount < 0
    amount = abs(amount)

    # Split into integer and decimal parts
    integer_part = int(amount)
    decimal_part = round(amount - integer_part, 2)

    s = str(integer_part)

    # Indian grouping: last 3 digits, then groups of 2
    if len(s) > 3:
        last_three = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        formatted = ",".join(groups) + "," + last_three
    else:
        formatted = s

    if decimal_part > 0:
        formatted += f".{int(round(decimal_part * 100)):02d}"

    prefix = "-₹" if is_negative else "₹"
    return f"{prefix}{formatted}"
