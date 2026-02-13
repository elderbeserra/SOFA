# UltraLight Face Detection Model — Training and Inference

This document describes the face detection model used by SOFA, its training technique, and how SOFA runs inference.

## 1. Model Overview

SOFA uses the **Ultra-Light-Fast-Generic-Face-Detector-1MB** (often called "UltraLight" or "Ultra Face").

| Property | Value |
|----------|--------|
| **Source** | [Linzaer/Ultra-Light-Fast-Generic-Face-Detector-1MB](https://github.com/Linzaer/Ultra-Light-Fast-Generic-Face-Detector-1MB) |
| **Task** | Face detection (bounding boxes + confidence) |
| **Architecture** | SSD-like detector with UltraLight backbone |
| **Input** | 640×480 or 320×240 RGB (NCHW, float32) |
| **Output** | Bounding boxes (normalized) and confidence scores |
| **Size** | ~1 MB (FP32 ONNX) |
| **File in SOFA** | `models/ultra_light_640.onnx` |

### Variants

- **version-slim**: Lighter, faster; MobileNetV1-based slim backbone.
- **version-RFB**: Receptive Field Block (RFB) module for multi-scale features; higher accuracy, slightly slower.

SOFA uses the 640×480 variant for a balance of speed and accuracy.

---

## 2. Training Technique

Training is **not** performed in the SOFA repository. It is done in the upstream project. The following describes the technique used there.

### Framework and Dataset

- **Framework**: PyTorch 1.2+
- **Dataset**: [WIDER FACE](http://shuoyang1213.me/WIDERFACE/) — 32,203 images, 393,703 labeled faces.
- **Format**: VOC-style (XML annotations); optional RetinaFace-filtered labels (faces smaller than 10×10 pixels removed for stability).

### Architecture

- **Backbone**: MobileNetV1-based ultra-light network (depthwise separable convolutions).
- **Detection head**: SSD-style multi-scale detection with classification and localization branches.
- **RFB variant**: Receptive Field Block layers to increase receptive field and improve multi-scale detection.

### Loss and Optimization

- **Loss**: Multi-task loss combining:
  - Classification loss (face vs. background).
  - Localization loss (bounding box regression, e.g. smooth L1).
- **Optimizer**: SGD with momentum.
- **Learning rate**: Typically ~0.001 with cosine annealing or step decay.
- **Batch size**: Often 24–32 depending on GPU memory.

### Data Augmentation

Common augmentations (as in similar face detection pipelines):

- Random crop and resize
- Horizontal flip
- Color jitter (brightness, contrast, saturation)

Exact scripts and hyperparameters are in the upstream repo (`train.py`, `train-version-slim.sh`, `train-version-RFB.sh`).

---

## 3. Training Process (Upstream)

To train or reproduce the model:

```bash
# Clone the training repository
git clone https://github.com/Linzaer/Ultra-Light-Fast-Generic-Face-Detector-1MB.git
cd Ultra-Light-Fast-Generic-Face-Detector-1MB

# Prepare WIDER FACE dataset in VOC format
# (See the repository's data preparation instructions)

# Train version-slim (faster) or version-RFB (more accurate)
bash train-version-slim.sh
# or
bash train-version-RFB.sh
```

Export to ONNX is done in that repository; the resulting `.onnx` file can be placed in SOFA’s `models/` directory.

---

## 4. Hyperparameters (Reference)

| Parameter | Typical value |
|-----------|----------------|
| Input size | 320×240 or 640×480 |
| Batch size | 24–32 |
| Learning rate | 0.001 |
| Optimizer | SGD + momentum |
| Schedule | Cosine annealing or step decay |

SOFA does not train the model; these are for reference when reading or re-running the upstream training code.

---

## 5. Inference Pipeline in SOFA

SOFA runs the model with ONNX Runtime (CPU or GPU). Pipeline:

1. **Load model**: `onnx.load()` + `onnx.checker.check_model()` + `ort.InferenceSession(model_path)`.
2. **Per frame**:
   - Resize frame to half resolution for processing (optional; SOFA does this for speed).
   - Resize to **640×480** for the network input.
   - Preprocess:
     - BGR → RGB.
     - Normalize: `(pixel - 127) / 128`.
     - Layout: NCHW, `float32`, batch size 1.
   - Run: `session.run(None, {input_name: img})` → `confidences`, `boxes`.
3. **Post-process** (in `UltraLightFaceRecog.predict()`):
   - Filter by confidence > `prob_threshold` (default **0.7**).
   - Hard NMS with **IoU threshold 0.5**.
   - Scale boxes from normalized [0,1] to frame coordinates (width, height).
4. **Anonymization**: Draw rectangles (or blur/pixelate) on the frame using the scaled boxes (e.g. with configurable padding, e.g. 10 px in the default implementation).

Relevant code: `src/face_recog.py` (`load_model`, `blur_faces`, `predict`, and anonymization loop).

---

## 6. Performance Benchmarks (Typical)

| Metric | Approximate value |
|--------|--------------------|
| Speed (320×240, CPU) | ~120 FPS on modern CPU |
| Speed (640×480, CPU) | Lower; depends on hardware |
| Accuracy (WIDER FACE Easy) | AP ~0.77 (refer to upstream papers/releases) |
| Model file size | ~1.5 MB (FP32 ONNX) |

Actual numbers depend on hardware and ONNX Runtime version (and GPU execution provider if enabled).

---

## 7. Fine-Tuning Guide

### When to Fine-Tune

- Domain shift: e.g. surveillance, sports, low light, non-frontal faces.
- Different demographics or face size distributions.
- Need for different precision/recall tradeoff on your data.

### Steps (High Level)

1. **Environment**: Use the upstream PyTorch repo and its dependencies.
2. **Data**: Annotate faces in your domain (VOC or same format as WIDER). Optionally filter very small faces (e.g. <10×10 px).
3. **Transfer learning**: Load the pretrained UltraLight weights, replace or adjust the detection head if the number of classes or anchors changed, then train with a small learning rate (e.g. 1e-4–1e-5).
4. **Export**: Export the fine-tuned model to ONNX using the upstream export script and replace `models/ultra_light_640.onnx` (or add a new model and point SOFA to it if supported).
5. **Evaluation**: Use standard metrics (e.g. AP on a held-out set, or precision/recall at a fixed confidence in SOFA’s pipeline).

### Evaluation Metrics

- **Precision / Recall** at a given confidence threshold.
- **Average Precision (AP)** on a labeled test set (e.g. WIDER-style splits or your own).
- **Inference speed** (FPS) in SOFA with your model and hardware.

---

## 8. References

- [Ultra-Light-Fast-Generic-Face-Detector-1MB](https://github.com/Linzaer/Ultra-Light-Fast-Generic-Face-Detector-1MB) — training and export code.
- [WIDER FACE](http://shuoyang1213.me/WIDERFACE/) — dataset used for training.
- [ONNX Runtime](https://onnxruntime.ai/) — inference engine used by SOFA.
