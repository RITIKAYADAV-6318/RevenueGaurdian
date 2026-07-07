import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

modules = [
    'agents.crm_agent',
    'agents.email_agent',
    'agents.calendar_agent',
    'agents.prediction_agent',
    'agents.recovery_agent',
    'agents.summary_agent',
    'agents.orchestrator'
]

for m in modules:
    try:
        __import__(m)
        print(f'OK: {m}')
    except Exception as e:
        print(f'ERR: {m} -> {e.__class__.__name__}: {e}')
        import traceback
        traceback.print_exc()
        break
