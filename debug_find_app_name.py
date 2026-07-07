import pathlib

root = pathlib.Path('C:/Users/ritik/AppData/Roaming/Python/Python314/site-packages')
needle = 'app_name is required when agent is provided without app'
for path in root.rglob('*.py'):
    try:
        text = path.read_text(errors='ignore')
    except Exception:
        continue
    if needle in text:
        print(path)
        start = text.index(needle)
        print(text[max(0, start-200):start+200])
        break
