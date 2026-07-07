import asyncio, traceback
from agents.orchestrator import RevOpsOrchestrator

async def main():
    try:
        orch = RevOpsOrchestrator()
        result = await orch.execute_workflow("debug_local")
        print("RESULT:", result)
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 