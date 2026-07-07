import inspect
import google.adk.types as types

print('types file:', types.__file__)
print('Message class exists:', hasattr(types, 'Message'))
print('Content class exists:', hasattr(types, 'Content'))
print('SystemMessage exists:', hasattr(types, 'SystemMessage'))
print('UserMessage exists:', hasattr(types, 'UserMessage'))
print('role names:', [name for name in dir(types) if 'Message' in name])
print('inspect.isawaitable exists:', hasattr(inspect, 'isawaitable'))
print('has asyncio.isawaitable:', hasattr(__import__('asyncio'), 'isawaitable'))
