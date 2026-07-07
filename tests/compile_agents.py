import py_compile
import glob

files = glob.glob('agents/*.py')
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print('OK:', f)
    except Exception as e:
        print('ERR:', f)
        import traceback
        traceback.print_exc()
        break
