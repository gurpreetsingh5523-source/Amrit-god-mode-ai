import sys


def read_file(file_path):
    try:
        with open(file_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return None
    except IOError as e:
        print(f"An error occurred while reading the file: {e}")
        return None


def write_file(file_path, content):
    try:
        with open(file_path, "w") as file:
            file.write(content)
    except IOError as e:
        print(f"An error occurred while writing to the file: {e}")


def fix_bugs_in_file(file_path):
    content = read_file(file_path)
    if content is None:
        return

    # Placeholder for actual bug-fixing logic
    fixed_content = content.replace(
        'print("Hello, World!")', 'print("Fixed Hello, World!")'
    )

    write_file(file_path, fixed_content)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python app.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    fix_bugs_in_file(file_path)
