import requests

# Test if backend is running
try:
    response = requests.get('http://127.0.0.1:5000/api/test')
    print(f"Backend test: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")