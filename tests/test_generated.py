import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel

# Assuming these are the classes and functions to test
class User(BaseModel):
    id: int
    name: str
    email: str
    age: Optional[int] = None
    balance: Decimal = Decimal('0.00')
    created_at: datetime = datetime.now()

class Order(BaseModel):
    id: int
    user_id: int
    items: List[str]
    total: Decimal
    status: str = "pending"

class UserService:
    def create_user(self, name: str, email: str, age: Optional[int] = None) -> User:
        if not name or not email:
            raise ValueError("Name and email are required")
        if age is not None and (age < 0 or age > 150):
            raise ValueError("Age must be between 0 and 150")
        return User(id=1, name=name, email=email, age=age)

    def get_user_orders(self, user_id: int) -> List[Order]:
        if user_id <= 0:
            raise ValueError("Invalid user ID")
        return [
            Order(id=1, user_id=user_id, items=["item1"], total=Decimal('100.00'))
        ]

    def calculate_discount(self, user: User, order_total: Decimal) -> Decimal:
        if order_total < 0:
            raise ValueError("Order total cannot be negative")
        if user.age and user.age >= 65:
            return order_total * Decimal('0.9')
        return order_total

def parse_date(date_string: str) -> datetime:
    if not date_string:
        raise ValueError("Date string cannot be empty")
    try:
        return datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_string}")

def divide_numbers(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b

def process_list(items: List[int]) -> List[int]:
    if not items:
        raise ValueError("List cannot be empty")
    return [x * 2 for x in items if x > 0]

class TestUserService:
    @pytest.fixture
    def user_service(self):
        return UserService()

    @pytest.fixture
    def sample_user(self):
        return User(id=1, name="John Doe", email="john@example.com", age=30)

    # Happy path tests
    def test_create_user_success(self, user_service):
        user = user_service.create_user("Alice", "alice@example.com", 25)
        assert user.name == "Alice"
        assert user.email == "alice@example.com"
        assert user.age == 25
        assert isinstance(user.balance, Decimal)
        assert isinstance(user.created_at, datetime)

    def test_create_user_without_age(self, user_service):
        user = user_service.create_user("Bob", "bob@example.com")
        assert user.name == "Bob"
        assert user.email == "bob@example.com"
        assert user.age is None

    def test_get_user_orders_success(self, user_service):
        orders = user_service.get_user_orders(1)
        assert len(orders) == 1
        assert isinstance(orders[0], Order)
        assert orders[0].user_id == 1
        assert orders[0].status == "pending"

    def test_calculate_discount_no_discount(self, user_service, sample_user):
        result = user_service.calculate_discount(sample_user, Decimal('100.00'))
        assert result == Decimal('100.00')

    def test_calculate_discount_senior_discount(self, user_service):
        senior_user = User(id=2, name="Senior", email="senior@example.com", age=70)
        result = user_service.calculate_discount(senior_user, Decimal('100.00'))
        assert result == Decimal('90.00')

    def test_calculate_discount_zero_total(self, user_service, sample_user):
        result = user_service.calculate_discount(sample_user, Decimal('0'))
        assert result == Decimal('0')

    # Edge cases
    def test_create_user_minimum_age(self, user_service):
        user = user_service.create_user("Young", "young@example.com", 0)
        assert user.age == 0

    def test_create_user_maximum_age(self, user_service):
        user = user_service.create_user("Old", "old@example.com", 150)
        assert user.age == 150

    def test_calculate_discount_edge_age(self, user_service):
        edge_user = User(id=3, name="Edge", email="edge@example.com", age=65)
        result = user_service.calculate_discount(edge_user, Decimal('100.00'))
        assert result == Decimal('90.00')

    # Error cases
    def test_create_user_empty_name(self, user_service):
        with pytest.raises(ValueError, match="Name and email are required"):
            user_service.create_user("", "email@example.com")

    def test_create_user_empty_email(self, user_service):
        with pytest.raises(ValueError, match="Name and email are required"):
            user_service.create_user("Name", "")

    def test_create_user_negative_age(self, user_service):
        with pytest.raises(ValueError, match="Age must be between 0 and 150"):
            user_service.create_user("Name", "email@example.com", -1)

    def test_create_user_age_too_high(self, user_service):
        with pytest.raises(ValueError, match="Age must be between 0 and 150"):
            user_service.create_user("Name", "email@example.com", 151)

    def test_get_user_orders_invalid_id(self, user_service):
        with pytest.raises(ValueError, match="Invalid user ID"):
            user_service.get_user_orders(0)

    def test_get_user_orders_negative_id(self, user_service):
        with pytest.raises(ValueError, match="Invalid user ID"):
            user_service.get_user_orders(-1)

    def test_calculate_discount_negative_total(self, user_service, sample_user):
        with pytest.raises(ValueError, match="Order total cannot be negative"):
            user_service.calculate_discount(sample_user, Decimal('-50.00'))

class TestParseDate:
    # Happy path tests
    def test_parse_date_valid(self):
        result = parse_date("2024-01-15")
        assert result == datetime(2024, 1, 15)

    def test_parse_date_leap_year(self):
        result = parse_date("2024-02-29")
        assert result == datetime(2024, 2, 29)

    def test_parse_date_first_day_of_year(self):
        result = parse_date("2024-01-01")
        assert result == datetime(2024, 1, 1)

    def test_parse_date_last_day_of_year(self):
        result = parse_date("2024-12-31")
        assert result == datetime(2024, 12, 31)

    # Edge cases
    def test_parse_date_future_date(self):
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        result = parse_date(future_date)
        assert isinstance(result, datetime)

    def test_parse_date_past_date(self):
        result = parse_date("1900-01-01")
        assert result == datetime(1900, 1, 1)

    # Error cases
    def test_parse_date_empty_string(self):
        with pytest.raises(ValueError, match="Date string cannot be empty"):
            parse_date("")

    def test_parse_date_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("15-01-2024")

    def test_parse_date_invalid_month(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2024-13-01")

    def test_parse_date_invalid_day(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2024-01-32")

    def test_parse_date_non_numeric(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2024-AB-CD")

class TestDivideNumbers:
    # Happy path tests
    def test_divide_positive_numbers(self):
        assert divide_numbers(10, 2) == 5.0

    def test_divide_negative_numbers(self):
        assert divide_numbers(-10, 2) == -5.0

    def test_divide_float_numbers(self):
        assert divide_numbers(10.5, 2.5) == 4.2

    def test_divide_by_one(self):
        assert divide_numbers(100, 1) == 100.0

    # Edge cases
    def test_divide_zero_by_number(self):
        with pytest.raises(ZeroDivisionError):
            divide_numbers(10, 0)