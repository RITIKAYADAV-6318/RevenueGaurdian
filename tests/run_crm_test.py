import asyncio
import traceback
import sys
import os

# Ensure project root is on sys.path for module imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from agents.crm_agent import run_crm_analysis

async def main():
    try:
        res = await run_crm_analysis()
        print('SUCCESS:', res)
    except Exception as e:
        print('EXCEPTION:')
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
