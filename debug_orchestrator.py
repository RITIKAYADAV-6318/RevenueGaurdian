import asyncio
from agents.orchestrator import RevOpsOrchestrator

async def main():
    orchestrator = RevOpsOrchestrator()
    try:
        result = await orchestrator.execute_workflow('test_run')
        print('STATUS:', result.status)
        print('HAS_SUMMARY:', result.executive_summary is not None)
        print('FAILURES:', result.failures)
    except Exception as ex:
        import traceback
        traceback.print_exc()

asyncio.run(main())
