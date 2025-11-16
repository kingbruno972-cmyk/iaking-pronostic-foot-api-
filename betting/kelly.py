def kelly_fraction(p: float, odds: float, b_mult: float = 0.25) -> float:
    b = odds - 1.0
    if b <= 0:
        return 0.0
    f = (p * b - (1 - p)) / b
    f = max(0.0, min(f, 1.0))
    return f * b_mult
