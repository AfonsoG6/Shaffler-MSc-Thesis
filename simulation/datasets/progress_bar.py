def readable_size(value: int) -> str:
    if value < 1024:
        return f'{value}B'
    elif value < 1024**2:
        return f'{value/1024:.2f}KB'
    elif value < 1024**3:
        return f'{value/1024**2:.2f}MB'
    else:
        return f'{value/1024**3:.2f}GB'


def print_progress_bar(current: int, total: int, max_bar_size: int = 80):
    bar_size = round(max_bar_size * current / total)
    print(f'[{"#"*bar_size}{"-"*(max_bar_size-bar_size)}] ({readable_size(current)}/{readable_size(total)}){" "*10}', end='\r', flush=True)
