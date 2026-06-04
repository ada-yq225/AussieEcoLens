from __future__ import annotations

import argparse
import json
import os
import site
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

from PIL import Image


CLASSES = [
    "Alectura_lathami",
    "Antechinus_agilis",
    "Bos_taurus",
    "Burhinus_grallarius",
    "Canis_familiaris",
    "Chalcophaps_longirostris",
    "Colluricincla_harmonica",
    "Corcorax_melanorhamphos",
    "Dacelo_novaeguineae",
    "Dama_dama",
    "Eopsaltria_australis",
    "Felis_catus",
    "Geopelia_humeralis",
    "Gymnorhina_tibicen",
    "Homo_sapiens",
    "Isoodon_macrourus",
    "Lepus_europaeus",
    "Macropus_giganteus",
    "Menura_novaehollandiae",
    "Mus_musculus",
    "Oryctolagus_cuniculus",
    "Perameles_nasuta",
    "Pitta_versicolor",
    "Rattus",
    "Rattus_fuscipes",
    "Rattus_rattus",
    "Strepera_graculina",
    "Sus_scrofa",
    "Tachyglossus_aculeatus",
    "Thylogale_stigmatica",
    "Trichosurus_caninus",
    "Trichosurus_cunninghami",
    "Trichosurus_vulpecula",
    "Varanus_varius",
    "Vombatus_ursinus",
    "Vulpes_vulpes",
    "Wallabia_bicolor",
    "Canis_dingo",
    "Capra_hircus",
    "Casuarius_casuarius",
    "Heteromyias_cinereifrons",
    "Hypsiprymnodon_moschatus",
    "Megapodius_reinwardt",
    "Notamacropus_rufogriseus",
    "Orthonyx_spaldingii",
    "Uromys_caudimaculatus",
]


def import_runtime():
    runtime_tmp = Path.cwd() / ".runtime_tmp"
    runtime_tmp.mkdir(exist_ok=True)
    os.environ.setdefault("YOLOV5_CONFIG_DIR", str(runtime_tmp / "yolov5"))
    os.environ.setdefault("MPLCONFIGDIR", str(runtime_tmp / "matplotlib"))
    os.environ.setdefault("YOLOv5_AUTOINSTALL", "false")
    for site_dir in site.getsitepackages():
        yolov5_dir = Path(site_dir) / "yolov5"
        if yolov5_dir.exists() and str(yolov5_dir) not in sys.path:
            sys.path.insert(0, str(yolov5_dir))
    try:
        import numpy as np
        import torch
        import torchvision.transforms as transforms
        from megadetector.detection import run_detector_batch
    except Exception as exc:
        raise SystemExit(
            "Missing model runtime. Use Python 3.12, then install: "
            "python -m pip install megadetector tqdm onnx2torch"
        ) from exc
    return np, torch, transforms, run_detector_batch


def crop_detections(image_path: Path, detections: List[Dict], output_dir: Path, threshold: float = 0.05) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    crops = []
    crop_num = 0
    for detection in detections:
        if detection.get("category") != "1" or float(detection.get("conf", 0)) < threshold:
            continue
        x, y, w, h = detection["bbox"]
        crop = img.crop((int(x * width), int(y * height), int((x + w) * width), int((y + h) * height)))
        crop = crop.resize((600, 600), Image.BILINEAR)
        target = output_dir / f"{image_path.stem}-{crop_num}{image_path.suffix}"
        crop.save(target)
        crops.append(target)
        crop_num += 1
    return crops


def classify_crop(crop: Path, model, torch, transforms, np, device: str) -> Dict:
    transform = transforms.Compose([transforms.Resize((480, 480)), transforms.ToTensor()])
    image = Image.open(crop).convert("RGB")
    tensor = transform(image).unsqueeze(0).permute(0, 2, 3, 1).to(device)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
    best = int(np.argsort(probs)[::-1][0])
    return {"crop": str(crop), "species": CLASSES[best], "confidence": float(probs[best])}


def predict(image_path: Path, model_path: Path, detector_path: Path) -> Dict:
    np, torch, transforms, run_detector_batch = import_runtime()
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    with tempfile.TemporaryDirectory() as tmp:
        detections = run_detector_batch.load_and_run_detector_batch(
            image_file_names=[str(image_path)],
            model_file=str(detector_path),
        )
        entry = detections[0]
        crop_dir = Path(tmp) / "crops"
        print("DEBUG DETECTIONS:", entry.get("detections", [])); crops = crop_detections(image_path, entry.get("detections", []), crop_dir)
        model = torch.load(model_path, map_location=device, weights_only=False)
        model.eval()
        model.to(device)
        predictions = [classify_crop(crop, model, torch, transforms, np, device) for crop in crops]
    return {"image": str(image_path), "predictions": predictions}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=Path("course_models/model.pt"))
    parser.add_argument("--detector", type=Path, default=Path("course_models/mdv5a.pt"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = predict(args.image, args.model, args.detector)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
