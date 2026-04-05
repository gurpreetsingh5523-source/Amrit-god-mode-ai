def calculate_expression(expression: str) -> float:
    """
    Evaluates a mathematical expression provided as a string.

    Args:
        expression (str): A mathematical expression.

    Returns:
        float: The result of the calculated expression.

    Raises:
        ValueError: If the expression contains invalid characters.
        ZeroDivisionError: If the division operation is attempted by zero.
    """
    try:
        # Validate the expression to only allow digits, operators and spaces
        if any(char not in "0123456789.+-*/() " for char in expression):
            raise ValueError("Invalid characters found in expression.")
        
        return eval(expression)
    except ZeroDivisionError as e:
        raise ZeroDivisionError("Cannot divide by zero.") from e
    except Exception as e:
        raise ValueError(f"An error occurred: {str(e)}")

def main():
    """
    Main function to allow user input of calculations and display results.
    """
    print("Welcome to the Calculator.")
    while True:
        try:
            user_input = input("Enter a calculation (or type 'exit' to quit): ").strip().lower()
            if user_input == "exit":
                print("Exiting the calculator. Goodbye!")
                break
            result = calculate_expression(user_input)
            print(f"The result is: {result}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()