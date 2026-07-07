import inspect
import pathlib
import google.adk.agents as mod
from google.adk.agents import Agent

print('Agent module:', mod.__file__)
print('Agent fields:', sorted(Agent.model_fields.keys()))

root = pathlib.Path(mod.__file__).resolve().parent
for path in root.rglob('*.py'):
    text = path.read_text(errors='ignore')
    if 'app_name' in text or 'app=' in text or 'LlmAgent' in text:
        print('---', path)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if 'app_name' in line or 'app=' in line or 'class LlmAgent' in line or 'LlmAgent' in line:
                start = max(0, i-3)
                end = min(len(lines), i+4)
                print('\n'.join(f'{j+1}: {lines[j]}' for j in range(start, end)))
        print()
