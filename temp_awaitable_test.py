import inspect

def gen():
    yield 1

print('isawaitable(gen()):', inspect.isawaitable(gen()))
print('iscoroutine(gen()):', inspect.iscoroutine(gen()))
print('isasyncgen(gen()):', inspect.isasyncgen(gen()))
print('has __await__:', hasattr(gen(), '__await__'))
