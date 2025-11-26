import requests
import json
import time

def check_server():
    url = "http://localhost:9090/tools"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("Server is running!")
            print("Tools available:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            return True
        else:
            print(f"Server returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Failed to connect to server: {e}")
        return False

if __name__ == "__main__":
    # Wait a bit for server to start
    time.sleep(2)
    check_server()
