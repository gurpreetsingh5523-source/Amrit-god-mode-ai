import api
from fastapi.testclient import TestClient
client = TestClient(api.app)

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


# Test root endpoint
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Expense Tracker API is running"}

# Test create expense
@patch("api.get_db")
def test_create_expense_success(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock cursor.lastrowid and fetchone
    mock_cursor.lastrowid = 1
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "amount": 100.50,
        "category": "Food",
        "description": "Groceries",
        "date": "2024-01-15"
    }
    
    # Test data
    expense_data = {
        "amount": 100.50,
        "category": "Food",
        "description": "Groceries",
        "date": "2024-01-15"
    }
    
    response = client.post("/expenses", json=expense_data)
    assert response.status_code == 201
    assert response.json()["id"] == 1
    assert response.json()["amount"] == 100.50
    assert response.json()["category"] == "Food"
    assert response.json()["description"] == "Groceries"
    assert response.json()["date"] == "2024-01-15"

@patch("api.get_db")
def test_create_expense_invalid_date(mock_get_db):
    # Test with invalid date format
    expense_data = {
        "amount": 100.50,
        "category": "Food",
        "description": "Groceries",
        "date": "15-01-2024"  # Wrong format
    }
    
    response = client.post("/expenses", json=expense_data)
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]

@patch("api.get_db")
def test_create_expense_database_error(mock_get_db):
    # Mock database connection to raise an error
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Make cursor.execute raise an exception
    from sqlite3 import Error as SQLiteError
    mock_cursor.execute.side_effect = SQLiteError("Database connection failed")
    
    expense_data = {
        "amount": 100.50,
        "category": "Food",
        "description": "Groceries",
        "date": "2024-01-15"
    }
    
    response = client.post("/expenses", json=expense_data)
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]

# Test get expenses
@patch("api.get_db")
def test_get_expenses_no_filter(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchall to return multiple expenses
    mock_cursor.fetchall.return_value = [
        {"id": 1, "amount": 100.50, "category": "Food", "description": "Groceries", "date": "2024-01-15"},
        {"id": 2, "amount": 50.00, "category": "Transport", "description": "Bus fare", "date": "2024-01-14"}
    ]
    
    response = client.get("/expenses")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["category"] == "Food"
    assert response.json()[1]["category"] == "Transport"

@patch("api.get_db")
def test_get_expenses_with_category_filter(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchall to return filtered expenses
    mock_cursor.fetchall.return_value = [
        {"id": 1, "amount": 100.50, "category": "Food", "description": "Groceries", "date": "2024-01-15"}
    ]
    
    response = client.get("/expenses?category=Food")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["category"] == "Food"

@patch("api.get_db")
def test_get_expenses_empty_result(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchall to return empty list
    mock_cursor.fetchall.return_value = []
    
    response = client.get("/expenses")
    assert response.status_code == 200
    assert response.json() == []

# Test get summary
@patch("api.get_db")
def test_get_summary_success(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchall to return category totals
    mock_cursor.fetchall.return_value = [
        {"category": "Food", "total": 250.75},
        {"category": "Transport", "total": 150.00}
    ]
    
    response = client.get("/summary")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["category"] == "Food"
    assert response.json()[0]["total"] == 250.75

@patch("api.get_db")
def test_get_summary_empty(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchall to return empty list
    mock_cursor.fetchall.return_value = []
    
    response = client.get("/summary")
    assert response.status_code == 200
    assert response.json() == []

# Test delete expense
@patch("api.get_db")
def test_delete_expense_success(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchone to return an existing expense
    mock_cursor.fetchone.return_value = {"id": 1}
    
    response = client.delete("/expenses/1")
    assert response.status_code == 204

@patch("api.get_db")
def test_delete_expense_not_found(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock fetchone to return None (expense not found)
    mock_cursor.fetchone.return_value = None
    
    response = client.delete("/expenses/999")
    assert response.status_code == 404
    assert "Expense not found" in response.json()["detail"]

@patch("api.get_db")
def test_delete_expense_database_error(mock_get_db):
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # First call to fetchone succeeds, but delete fails
    mock_cursor.fetchone.return_value = {"id": 1}
    from sqlite3 import Error as SQLiteError
    mock_cursor.execute.side_effect = [None, SQLiteError("Database error")]
    
    response = client.delete("/expenses/1")
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]