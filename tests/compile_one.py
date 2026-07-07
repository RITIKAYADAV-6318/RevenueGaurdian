import py_compile
import traceback

f = 'agents/calendar_agent.py'
try:
    py_compile.compile(f, doraise=True)
    print('OK:', f)
except Exception as e:
    print('ERR:', type(e).__name__, e)
    traceback.print_exc()
