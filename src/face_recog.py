import argparse
import csv
import os

import cv2
import numpy as np
import numpy.typing as npt
import onnx
import onnxruntime as ort

from .settings import (
    AnonymizationMode,
    get_anonymization_mode,
    get_blur_strength,
    get_box_padding,
    get_confidence_threshold,
    get_gpu_provider,
    get_output_scale,
)
from .signals import SignalBus

MODEL_PATH = './models/ultra_light_640.onnx'


class UltraLightFaceRecog:
    def __init__(self) -> None:
        self.comm = SignalBus.instance()
        self.running: bool = True

    def area_of(
        self,
        left_top: npt.NDArray[np.floating],
        right_bottom: npt.NDArray[np.floating],
    ) -> npt.NDArray[np.floating]:
        """
        Compute the areas of rectangles given two corners.
        Args:
            left_top (N, 2): left top corner.
            right_bottom (N, 2): right bottom corner.
        Returns:
            area (N): return the area.
        """
        hw = np.clip(right_bottom - left_top, 0.0, None)
        return hw[..., 0] * hw[..., 1]

    def iou_of(
        self,
        boxes0: npt.NDArray[np.floating],
        boxes1: npt.NDArray[np.floating],
        eps: float = 1e-5,
    ) -> npt.NDArray[np.floating]:
        """
        Return intersection-over-union (Jaccard index) of boxes.
        Args:
            boxes0 (N, 4): ground truth boxes.
            boxes1 (N or 1, 4): predicted boxes.
            eps: a small number to avoid 0 as denominator.
        Returns:
            iou (N): IoU values.
        """
        overlap_left_top = np.maximum(boxes0[..., :2], boxes1[..., :2])
        overlap_right_bottom = np.minimum(boxes0[..., 2:], boxes1[..., 2:])

        overlap_area = self.area_of(overlap_left_top, overlap_right_bottom)
        area0 = self.area_of(boxes0[..., :2], boxes0[..., 2:])
        area1 = self.area_of(boxes1[..., :2], boxes1[..., 2:])
        return overlap_area / (area0 + area1 - overlap_area + eps)

    def hard_nms(
        self,
        box_scores: npt.NDArray[np.floating],
        iou_threshold: float,
        top_k: int = -1,
        candidate_size: int = 200,
    ) -> npt.NDArray[np.floating]:
        """
        Perform hard non-maximum-supression to filter out boxes with iou greater
        than threshold
        Args:
            box_scores (N, 5): boxes in corner-form and probabilities.
            iou_threshold: intersection over union threshold.
            top_k: keep top_k results. If k <= 0, keep all the results.
            candidate_size: only consider the candidates with the highest scores.
        Returns:
            picked: a list of indexes of the kept boxes
        """
        scores = box_scores[:, -1]
        boxes = box_scores[:, :-1]
        picked = []
        indexes = np.argsort(scores)
        indexes = indexes[-candidate_size:]
        while len(indexes) > 0:
            current = indexes[-1]
            picked.append(current)
            if 0 < top_k == len(picked) or len(indexes) == 1:
                break
            current_box = boxes[current, :]
            indexes = indexes[:-1]
            rest_boxes = boxes[indexes, :]
            iou = self.iou_of(
                rest_boxes,
                np.expand_dims(current_box, axis=0),
            )
            indexes = indexes[iou <= iou_threshold]

        return box_scores[picked, :]

    def predict(
        self,
        width: int,
        height: int,
        confidences: npt.NDArray[np.floating],
        boxes: npt.NDArray[np.floating],
        prob_threshold: float,
        iou_threshold: float = 0.5,
        top_k: int = -1,
    ) -> tuple[npt.NDArray[np.int32], npt.NDArray, npt.NDArray[np.floating]]:
        """
        Select boxes that contain human faces
        Args:
            width: original image width
            height: original image height
            confidences (N, 2): confidence array
            boxes (N, 4): boxes array in corner-form
            iou_threshold: intersection over union threshold.
            top_k: keep top_k results. If k <= 0, keep all the results.
        Returns:
            boxes (k, 4): an array of boxes kept
            labels (k): an array of labels for each boxes kept
            probs (k): an array of probabilities for each boxes being in
            corresponding labels
        """
        boxes = boxes[0]
        confidences = confidences[0]
        picked_box_probs: list[npt.NDArray[np.floating]] = []
        picked_labels: list[int] = []
        for class_index in range(1, confidences.shape[1]):
            probs = confidences[:, class_index]
            mask = probs > prob_threshold
            probs = probs[mask]
            if probs.shape[0] == 0:
                continue
            subset_boxes = boxes[mask, :]
            box_probs = np.concatenate([subset_boxes, probs.reshape(-1, 1)], axis=1)
            box_probs = self.hard_nms(
                box_probs,
                iou_threshold=iou_threshold,
                top_k=top_k,
            )
            picked_box_probs.append(box_probs)
            picked_labels.extend([class_index] * box_probs.shape[0])
        if not picked_box_probs:
            return np.array([]), np.array([]), np.array([])
        picked_box_probs_arr = np.concatenate(picked_box_probs)
        picked_box_probs_arr[:, 0] *= width
        picked_box_probs_arr[:, 1] *= height
        picked_box_probs_arr[:, 2] *= width
        picked_box_probs_arr[:, 3] *= height
        return (
            picked_box_probs_arr[:, :4].astype(np.int32),
            np.array(picked_labels),
            picked_box_probs_arr[:, 4],
        )

    def load_model(self, model_path: str) -> None:
        onnx_model = onnx.load(model_path)
        onnx.checker.check_model(onnx_model)
        provider = get_gpu_provider()
        providers: list[str] = []
        if provider:
            providers.append(provider)
        providers.append('CPUExecutionProvider')
        try:
            self.ort_session = ort.InferenceSession(
                model_path, providers=providers
            )
        except (ValueError, RuntimeError):
            self.ort_session = ort.InferenceSession(model_path)
        self.input_name = self.ort_session.get_inputs()[0].name

    def stop(self) -> None:
        self.running = False

    def _apply_anonymization(
        self,
        frame: npt.NDArray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        mode: AnonymizationMode,
        padding: int,
        blur_strength: int,
    ) -> None:
        h, w = frame.shape[:2]
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(w, x2 + padding)
        y2 = min(h, y2 + padding)
        if x1 >= x2 or y1 >= y2:
            return
        roi = frame[y1:y2, x1:x2]
        if mode == AnonymizationMode.BLACK_BOX:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), -1)
        elif mode == AnonymizationMode.BLUR:
            k = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
            blurred = cv2.GaussianBlur(roi, (k, k), 0)
            frame[y1:y2, x1:x2] = blurred
        elif mode == AnonymizationMode.PIXELATE:
            scale = max(1, min(roi.shape[0], roi.shape[1]) // 12)
            small_h, small_w = max(1, (y2 - y1) // scale), max(1, (x2 - x1) // scale)
            small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
            pixelated = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
            frame[y1:y2, x1:x2] = pixelated

    def blur_faces(self, video_input: str, video_output: str) -> None:
        self.load_model(MODEL_PATH)
        video = cv2.VideoCapture(video_input)
        n_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or not np.isfinite(fps):
            fps = 30.0
        frame_ctr = 0
        ret, frame = video.read()
        height, width, layers = frame.shape
        scale = get_output_scale()
        new_h = int(height * scale)
        new_w = int(width * scale)
        size = (new_w, new_h)
        mode = get_anonymization_mode()
        padding = get_box_padding()
        blur_strength = get_blur_strength()
        prob_threshold = get_confidence_threshold()
        all_frames: list[npt.NDArray] = []
        metadata_rows: list[tuple[int, int]] = []
        while self.running:
            ret, frame = video.read()
            frame_ctr += 1
            self.comm.updProgress.emit(100 * frame_ctr / n_frames)
            if frame is not None:
                frame = cv2.resize(frame, (new_w, new_h))
                h, w, _ = frame.shape
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = cv2.resize(img, (640, 480))
                img_mean = np.array([127, 127, 127])
                img = (img - img_mean) / 128
                img = np.transpose(img, [2, 0, 1])
                img = np.expand_dims(img, axis=0)
                img = img.astype(np.float32)

                confidences, boxes = self.ort_session.run(None, {self.input_name: img})
                boxes, labels, probs = self.predict(w, h, confidences, boxes, prob_threshold)
                face_count = int(boxes.shape[0])
                metadata_rows.append((len(all_frames), face_count))
                for i in range(boxes.shape[0]):
                    box = boxes[i, :]
                    x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                    self._apply_anonymization(
                        frame, x1, y1, x2, y2, mode, padding, blur_strength
                    )
                all_frames.append(frame)
            else:
                break
        if self.running:
            self.save_local_video(all_frames, video_output, fps, size)
            self._write_metadata_csv(video_output, metadata_rows)
            self.comm.videoProcessed.emit()

    def save_local_video(
        self,
        frames_array: list[npt.NDArray],
        filepath: str,
        fps: float,
        size: tuple[int, int],
    ) -> None:
        out = cv2.VideoWriter(
            filepath, cv2.VideoWriter_fourcc(*'mp4v'), round(fps) or 30, size
        )
        print('Frames array size: ', len(frames_array))
        for frame in frames_array:
            out.write(frame)

        out.release()
        print('> Video saved at ', filepath)

    def _write_metadata_csv(self, video_output: str, metadata_rows: list[tuple[int, int]]) -> None:
        """Write timeline metadata CSV next to the processed video (frame_num, diff)."""
        if not metadata_rows:
            return
        base, _ = os.path.splitext(video_output)
        csv_path = base + '.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['frame_num', 'diff'])
            for frame_num, diff in metadata_rows:
                writer.writerow([frame_num, diff])
        print('> Metadata CSV saved at ', csv_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i',
        '--video_input',
        help='Input video path',
        default='',
        dest='video_input',
    )
    parser.add_argument(
        '-o',
        '--video_output',
        help='Output video path',
        default='',
        dest='video_output',
    )
    args = parser.parse_args()

    face_recog = UltraLightFaceRecog()
    face_recog.blur_faces(args.video_input, args.video_output)
