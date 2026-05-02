import time

def fibonacci_memoization(n, memo={}):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fibonacci_memoization(n-1, memo) + fibonacci_memoization(n-2, memo)
    return memo[n]

# Example usage:
if __name__ == "__main__":
    start_time = time.time()
    print(fibonacci_memoization(35))  # Change the number to test other values
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")