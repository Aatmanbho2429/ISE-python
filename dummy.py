# export_clip.py
import torch
from transformers import CLIPVisionModel

model = CLIPVisionModel.from_pretrained("openai/clip-vit-base-patch32")
model.eval()

class Encoder(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        out = self.model(pixel_values=x)
        emb = out.pooler_output          # [batch, 768] → projected below
        emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.float()

encoder = Encoder(model)
encoder.eval()

dummy = torch.zeros(1, 3, 224, 224)
with torch.no_grad():
    test = encoder(dummy)
    print(f"Output shape: {test.shape}")  # Must be [1, 768]

torch.onnx.export(
    encoder,
    dummy,
    "clip_vitb32.onnx",
    input_names=["pixel_values"],
    output_names=["embeddings"],
    dynamic_axes={
        "pixel_values": {0: "batch"},
        "embeddings":   {0: "batch"}
    },
    opset_version=14,
    do_constant_folding=True
)
print("Exported successfully")