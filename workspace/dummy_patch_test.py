print("dummy_patch_test.py")

def broken_func():
    print("missing colon")  # Fixed: added missing colon

if __name__ == "__main__":
    try:
        broken_func()
    except SyntaxError as e:
        print(f"Syntax Error: {e}")