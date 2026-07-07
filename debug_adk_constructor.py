import inspect
import google.adk.agents as mod
from google.adk.agents import Agent

print('module file:', mod.__file__)
print('Agent signature:', inspect.signature(Agent))
print('Agent __init__:', inspect.getsource(Agent.__init__))
