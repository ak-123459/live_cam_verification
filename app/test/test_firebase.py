from app.auth.firebase_auth import firebase_auth

success, message, uid = firebase_auth.create_user(
    email="test@aptalai.com",
    password="Test123!",
    display_name="Test User"
)

if success:
    print(f"✓ User created: {uid}")
else:
    print(f"✗ Error: {message}")
