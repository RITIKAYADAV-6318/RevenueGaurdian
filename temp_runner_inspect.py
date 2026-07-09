import os, inspect, itertools
from agents.crm_agent import create_crm_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

os.chdir(r'c:\Users\ritik\OneDrive\Desktop\SummerGrind26\AI AGENTS 5 DAYS KAGGLE\CapstoneProject')

agent = create_crm_agent()
runner = Runner(agent=agent, session_service=InMemorySessionService(), app_name='revenue_guardian', auto_create_session=True)
new_message = types.Content(parts=[types.Part.from_text(text='hi')], role='user')
raw = runner.run(user_id='system', session_id='crm_analysis_session', new_message=new_message)
print('raw type:', type(raw))
print('inspect.isawaitable:', inspect.isawaitable(raw))
print('inspect.isgenerator:', inspect.isgenerator(raw))
print('inspect.isasyncgen:', inspect.isasyncgen(raw))
print('has __await__:', hasattr(raw, '__await__'))
for idx, item in enumerate(itertools.islice(raw, 5)):
    print('--- item', idx, type(item))
    print('has_content', hasattr(item, 'content'))
    print('has_output', hasattr(item, 'output'))
    print('has_structured_output', hasattr(item, 'structured_output'))
    print('attrs', [a for a in dir(item) if not a.startswith('_')][:60])
    print('content repr:', repr(getattr(item, 'content', None))[:400])
    print('output repr:', repr(getattr(item, 'output', None))[:400])
    print('structured_output repr:', repr(getattr(item, 'structured_output', None))[:400])
    break
