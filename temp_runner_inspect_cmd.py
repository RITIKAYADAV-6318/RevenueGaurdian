import os
import inspect
from itertools import islice
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from agents.crm_agent import create_crm_agent
from google.genai import types

os.chdir(r'C:/Users/ritik/OneDrive/Desktop/SummerGrind26/AI AGENTS 5 DAYS KAGGLE/CapstoneProject')
agent = create_crm_agent()
runner = Runner(agent=agent, session_service=InMemorySessionService(), app_name='revenue_guardian', auto_create_session=True)
new_message = types.Content(parts=[types.Part.from_text(text='hi')], role='user')
raw = runner.run(user_id='system', session_id='crm_analysis_session', new_message=new_message)
print('raw type:', type(raw))
print('inspect.isawaitable:', inspect.isawaitable(raw))
print('inspect.isgenerator:', inspect.isgenerator(raw))
print('inspect.isasyncgen:', inspect.isasyncgen(raw))
for idx, item in enumerate(islice(raw, 5)):
    print('--- item', idx, type(item))
    print('has_structured_output', hasattr(item, 'structured_output'))
    print('has_output', hasattr(item, 'output'))
    print('has_content', hasattr(item, 'content'))
    print('structured_output', getattr(item, 'structured_output', None))
    print('output', getattr(item, 'output', None))
    print('content', getattr(item, 'content', None))
    print('repr output', repr(getattr(item, 'output', None))[:500])
    print('repr content', repr(getattr(item, 'content', None))[:500])
    print()
