# export_clip.py
import torch
import os
from transformers import CLIPVisionModel

model = CLIPVisionModel.from_pretrained("openai/clip-vit-base-patch32")
model.eval()

class Encoder(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        out = self.model(pixel_values=x)
        emb = out.pooler_output
        emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.float()

encoder = Encoder(model)
encoder.eval()

dummy = torch.zeros(1, 3, 224, 224)
with torch.no_grad():
    test = encoder(dummy)
    print(f"Output shape: {test.shape}")

torch.onnx.export(
    encoder,
    dummy,
    "models/clip_vitb32.onnx",
    input_names=["pixel_values"],
    output_names=["embeddings"],
    dynamic_axes={
        "pixel_values": {0: "batch"},
        "embeddings":   {0: "batch"}
    },
    opset_version=14,
    do_constant_folding=True
)

# ── Force merge external data into single file ──────────────────
import onnx
from onnx.external_data_helper import convert_model_to_external_data, load_external_data_for_model

print("Loading exported model...")
model_onnx = onnx.load("models/clip_vitb32.onnx", load_external_data=True)

print("Saving as single file...")
onnx.save(
    model_onnx,
    "models/clip_vitb32.onnx",
    save_as_external_data=False   # ← forces everything into ONE file
)

print("✅ Single file saved!")
print(f"Size: {os.path.getsize('models/clip_vitb32.onnx') / 1024 / 1024:.1f} MB")