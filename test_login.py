import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.auth_service import login

print("Testing login...")
result = login("test@gmail.com", "Test@123")

print(f"Success  : {result.success}")
print(f"Message  : {result.message}")
print(f"User     : {result.user}")

if result.success:
    print("\n✅ Login works!")
    from app.core.embedder import Embedder
    print(f"Model ready: {Embedder().is_ready}")
else:
    print("\n❌ Login failed — check error above")