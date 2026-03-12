# merge_model.py
import os
import onnx

print("Loading model with external data...")
# Must load from the folder where both files are
os.chdir("models")
model = onnx.load("clip_vitb32.onnx", load_external_data=True)

print("Saving as single file...")
os.chdir("..")
onnx.save_model(
    model,
    "models/clip_vitb32_single.onnx",
    save_as_external_data=False
)

size = os.path.getsize("models/clip_vitb32_single.onnx") / 1024 / 1024
print(f"✅ Done! Single file: {size:.1f} MB")
print("Files in models/:")
for f in os.listdir("models"):
    print(f"  {f}")