#!/usr/bin/env python3
"""
Test script for Skymarshal and Litemarshal web interfaces.
This script tests both interfaces to ensure they work correctly.
"""

import requests
import time
import json
import sys
from urllib.parse import urljoin

# Configuration
SKYMARSHAL_URL = "http://localhost:5058"
LITEMARSHAL_URL = "http://localhost:5050"

def test_endpoint(url, endpoint, method="GET", data=None, expected_status=200):
    """Test a single endpoint"""
    full_url = urljoin(url, endpoint)
    
    try:
        if method == "GET":
            response = requests.get(full_url, timeout=10)
        elif method == "POST":
            response = requests.post(full_url, json=data, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status_code == expected_status:
            print(f"✅ {method} {endpoint} - Status: {response.status_code}")
            return True
        else:
            print(f"❌ {method} {endpoint} - Expected: {expected_status}, Got: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ {method} {endpoint} - Error: {e}")
        return False

def test_skymarshal():
    """Test Skymarshal full interface"""
    print("\n🚀 Testing Skymarshal (Full Interface)")
    print("=" * 50)
    
    tests = [
        ("/", "GET", None, 200),  # Should redirect to login
        ("/skymarshal/login", "GET", None, 200),  # Login page
        ("/skymarshal/setup", "GET", None, 200),  # Setup page (shows when not authenticated)
        ("/skymarshal/dashboard", "GET", None, 200),  # Dashboard (shows when not authenticated)
        ("/skymarshal/nuke", "GET", None, 200),  # Nuclear delete page (shows when not authenticated)
        ("/skymarshal/bluesky-facts", "GET", None, 200),  # Facts page (shows when not authenticated)
        ("/skymarshal/user-profile", "GET", None, 200),  # Profile page (shows when not authenticated)
        ("/skymarshal/search", "POST", {"keyword": "test"}, 401),  # Should return 401 (not authenticated)
        ("/skymarshal/delete", "POST", {"uris": ["test"]}, 401),  # Should return 401 (not authenticated)
        ("/skymarshal/health", "GET", None, 404),  # Health endpoint doesn't exist
    ]
    
    passed = 0
    total = len(tests)
    
    for endpoint, method, data, expected_status in tests:
        if test_endpoint(SKYMARSHAL_URL, endpoint, method, data, expected_status):
            passed += 1
    
    print(f"\n📊 Skymarshal Results: {passed}/{total} tests passed")
    return passed == total

def test_litemarshal():
    """Test Litemarshal lightweight interface"""
    print("\n⚡ Testing Litemarshal (Lightweight Interface)")
    print("=" * 50)
    
    tests = [
        ("/", "GET", None, 200),  # Should redirect to login
        ("/litemarshal/lite/login", "GET", None, 200),  # Login page
        ("/litemarshal/lite", "GET", None, 200),  # Dashboard (shows when not authenticated)
        ("/litemarshal/lite/health", "GET", None, 200),  # Health endpoint
        ("/litemarshal/lite/search", "POST", {"keyword": "test"}, 401),  # Should return 401 (not authenticated)
        ("/litemarshal/lite/delete", "POST", {"uris": ["test"]}, 401),  # Should return 401 (not authenticated)
        ("/litemarshal/lite/refresh", "POST", None, 401),  # Should return 401 (not authenticated)
    ]
    
    passed = 0
    total = len(tests)
    
    for endpoint, method, data, expected_status in tests:
        if test_endpoint(LITEMARSHAL_URL, endpoint, method, data, expected_status):
            passed += 1
    
    print(f"\n📊 Litemarshal Results: {passed}/{total} tests passed")
    return passed == total

def test_static_files():
    """Test static file serving"""
    print("\n📁 Testing Static Files")
    print("=" * 50)
    
    static_tests = [
        (SKYMARSHAL_URL, "/skymarshal/static/css/style.css"),
        (SKYMARSHAL_URL, "/skymarshal/static/js/main.js"),
        (LITEMARSHAL_URL, "/litemarshal/static/css/lite.css"),
    ]
    
    passed = 0
    total = len(static_tests)
    
    for base_url, static_path in static_tests:
        full_url = urljoin(base_url, static_path)
        try:
            response = requests.get(full_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {static_path} - Status: {response.status_code}")
                passed += 1
            else:
                print(f"❌ {static_path} - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {static_path} - Error: {e}")
    
    print(f"\n📊 Static Files Results: {passed}/{total} tests passed")
    return passed == total

def test_services_running():
    """Test if both services are running"""
    print("\n🔍 Checking Service Status")
    print("=" * 50)
    
    services = [
        ("Skymarshal", SKYMARSHAL_URL),
        ("Litemarshal", LITEMARSHAL_URL),
    ]
    
    all_running = True
    
    for name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code in [200, 302]:  # 302 is OK for redirects
                print(f"✅ {name} is running on {url}")
            else:
                print(f"⚠️ {name} responded with status {response.status_code}")
                all_running = False
        except requests.exceptions.RequestException as e:
            print(f"❌ {name} is not running on {url} - Error: {e}")
            all_running = False
    
    return all_running

def main():
    """Run all tests"""
    print("🧪 Skymarshal & Litemarshal Web Interface Test Suite")
    print("=" * 60)
    
    # Check if services are running
    if not test_services_running():
        print("\n❌ One or more services are not running. Please start them first:")
        print("   cd skymarshal/web && python app.py &")
        print("   cd skymarshal/web && python lite_app.py &")
        sys.exit(1)
    
    # Run tests
    skymarshal_ok = test_skymarshal()
    litemarshal_ok = test_litemarshal()
    static_ok = test_static_files()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    print(f"Skymarshal (Full): {'✅ PASS' if skymarshal_ok else '❌ FAIL'}")
    print(f"Litemarshal (Lite): {'✅ PASS' if litemarshal_ok else '❌ FAIL'}")
    print(f"Static Files: {'✅ PASS' if static_ok else '❌ FAIL'}")
    
    all_passed = skymarshal_ok and litemarshal_ok and static_ok
    
    if all_passed:
        print("\n🎉 All tests passed! Both interfaces are working correctly.")
        print("\n🌐 Access URLs:")
        print(f"   Skymarshal (Full): {SKYMARSHAL_URL}")
        print(f"   Litemarshal (Lite): {LITEMARSHAL_URL}")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()