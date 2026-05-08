DEFAULT_PER_PAGE = 25
PAGE_SIZE_OPTIONS = (25, 50, 100)


def normalize_per_page(value: str | None) -> int:
    try:
        per_page = int(value or "")
    except TypeError, ValueError:
        return DEFAULT_PER_PAGE
    return per_page if per_page > 0 else DEFAULT_PER_PAGE


def page_size_options_for(per_page: int) -> list[int]:
    options = list(PAGE_SIZE_OPTIONS)
    if per_page not in options:
        options.append(per_page)
        options.sort()
    return options
