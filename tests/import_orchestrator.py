import sys, os, traceback
sys.path.append(os.path.abspath('.'))
try:
    import agents.orchestrator as orch
    print('OK: imported orchestrator')
except Exception as e:
    print('ERR:', type(e).__name__, e)
    traceback.print_exc()
