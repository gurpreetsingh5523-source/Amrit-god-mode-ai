import sys

if 'python' in sys.modules:
    print("Python module is already imported.")
else:
    try:
        import python
    except ImportError:
        print("Failed to import python module.")

# Your other code here