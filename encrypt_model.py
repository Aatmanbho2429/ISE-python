from cryptography.fernet import Fernet

# Paste your key here — same one you saved in Supabase
KEY = "WsjDf-7j5Lvv_mLE4d35rNn48AAhJS13iETh3E0n-ag="

fernet = Fernet(KEY.encode())

# Read original model
with open("models/clip_vitb32.onnx", "rb") as f:
    original = f.read()

# Encrypt it
encrypted = fernet.encrypt(original)

# Save encrypted version
with open("models/clip_vitb32.onnx.enc", "wb") as f:
    f.write(encrypted)

print("✅ Model encrypted successfully!")
print("✅ clip_vitb32.onnx.enc created in models folder")
print("⚠️  Now DELETE clip_vitb32.onnx — never ship the original!")