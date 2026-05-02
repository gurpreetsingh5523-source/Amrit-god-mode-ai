import re


def natural_language_to_structured(query):
    # Convert to lowercase for uniformity
    query = query.lower()

    # Extracting entities: name, age, email
    entity_pattern = r"(?P<entity>\bname|age|email\b)\s*:\s*(?P<value>.+)"
    entities = re.findall(entity_pattern, query)
    structured_data = {entity: value.strip() for entity, value in entities}

    # Extracting questions: what is name/age/email?
    question_pattern = r"what\s*is\s*\bname|age|email\b\?"
    questions = re.findall(question_pattern, query, re.IGNORECASE)
    structured_data["query"] = ", ".join(questions)

    return structured_data


# Example usage
if __name__ == "__main__":
    try:
        user_query = "find me the name, it is John and my email is john@example.com. what is age?"
        result = natural_language_to_structured(user_query)
        print(result)
    except Exception as e:
        print(f"An error occurred: {e}")
