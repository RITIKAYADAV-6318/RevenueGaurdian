import pathlib
root = pathlib.Path(r'C:/Users/ritik/AppData/Roaming/Python/Python314/site-packages/google/adk')
target = root / 'runners.py'
text = target.read_text()
needle = 'app_name'
for i, line in enumerate(text.splitlines(), start=1):
    if needle in line:
        start = max(1, i-3)
        end = min(len(text.splitlines()), i+3)
        print(f'--- {target}:{i}')
        for j in range(start, end+1):
            print(f'{j}: {text.splitlines()[j-1]}')
        print()
