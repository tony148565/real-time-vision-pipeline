import cv2
import multiprocessing as mp
import time
import queue
import json
import numpy as np


CONFIG_PATH = "config.json"


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def capture_process(frame_queue, meta_queue, config):
    video_source = config["video_source"]
    loop_video = config.get("loop_video", False)

    cap = cv2.VideoCapture(video_source)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    meta_queue.put(fps)
    delay = 1.0 / fps

    try:
        while True:
            start = time.time()
            ret, frame = cap.read()

            if not ret:
                if loop_video:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    # sentinel: 通知下游結束
                    try:
                        frame_queue.put_nowait(None)
                    except queue.Full:
                        pass
                    break

            try:
                if frame_queue.full():
                    # 丟棄舊 frame，避免延遲累積
                    frame_queue.get_nowait()
                frame_queue.put_nowait(frame)
            except queue.Empty:
                pass
            except queue.Full:
                pass

            elapsed = time.time() - start
            time.sleep(max(0.0, delay - elapsed))
    finally:
        cap.release()


def build_roi_points(frame_width, frame_height, roi_points_ratio):
    points = []
    for x_ratio, y_ratio in roi_points_ratio:
        x = int(frame_width * x_ratio)
        y = int(frame_height * y_ratio)
        points.append([x, y])
    return np.array(points, dtype=np.int32)


def process_process(frame_queue, result_queue, record_queue, config):
    roi_points_ratio = config["roi_points_ratio"]
    low_ratio = config.get("low_ratio", 0.05)
    high_ratio = config.get("high_ratio", 0.15)
    canny_threshold_1 = config.get("canny_threshold_1", 100)
    canny_threshold_2 = config.get("canny_threshold_2", 200)
    overlay_alpha = config.get("overlay_alpha", 0.2)

    while True:
        try:
            frame = frame_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if frame is None:
            # 將 sentinel 往下游傳遞
            try:
                result_queue.put_nowait(None)
            except queue.Full:
                pass

            try:
                record_queue.put_nowait(None)
            except queue.Full:
                pass
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, canny_threshold_1, canny_threshold_2)

        h, w = edges.shape
        roi_points = build_roi_points(w, h, roi_points_ratio)

        mask = np.zeros_like(edges)
        cv2.fillPoly(mask, [roi_points], 255)

        roi_edges = cv2.bitwise_and(edges, mask)
        edge_count = cv2.countNonZero(roi_edges)
        roi_area = cv2.countNonZero(mask)
        activity_ratio = edge_count / roi_area if roi_area > 0 else 0.0

        if activity_ratio < low_ratio:
            activity = "LOW"
        elif activity_ratio < high_ratio:
            activity = "MEDIUM"
        else:
            activity = "HIGH"

        display_frame = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        overlay = display_frame.copy()
        cv2.fillPoly(overlay, [roi_points], (0, 255, 0))
        display_frame = cv2.addWeighted(
            overlay, overlay_alpha, display_frame, 1 - overlay_alpha, 0
        )

        cv2.polylines(
            display_frame,
            [roi_points],
            isClosed=True,
            color=(0, 255, 0),
            thickness=2
        )

        result_item = (display_frame, edge_count, activity, activity_ratio)

        try:
            if result_queue.full():
                result_queue.get_nowait()
            result_queue.put_nowait(result_item)
        except queue.Empty:
            pass
        except queue.Full:
            pass

        try:
            if not record_queue.full():
                record_queue.put_nowait((display_frame, edge_count, activity, activity_ratio))
        except queue.Full:
            pass


def record_process(record_queue, meta_queue, config):
    record_output = config.get("record_output", True)
    output_path = config.get("output_path", "output.mp4")
    show_fps = config.get("show_fps", True)
    output_bar_max_ratio = config.get("output_bar_max_ratio", 0.25)

    writer = None
    source_fps = meta_queue.get()

    try:
        while True:
            try:
                item = record_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:
                break

            if not record_output:
                continue

            frame, edge_count, activity, activity_ratio = item

            output_frame = draw_overlay(
                frame=frame,
                fps=source_fps,
                edge_count=edge_count,
                activity=activity,
                activity_ratio=activity_ratio,
                show_fps=show_fps,
                output_bar_max_ratio=output_bar_max_ratio
            )

            if writer is None:
                h, w = output_frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(output_path, fourcc, source_fps, (w, h))

            writer.write(output_frame)
    finally:
        if writer is not None:
            writer.release()

def draw_overlay(frame, fps, edge_count, activity, activity_ratio, show_fps, output_bar_max_ratio):
    output = frame.copy()

    if show_fps:
        cv2.putText(
            output,
            f"FPS: {fps:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

    cv2.putText(
        output,
        f"Edge Count: {edge_count}",
        (10, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 0),
        2
    )

    cv2.putText(
        output,
        f"Traffic Level: {activity}",
        (10, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2
    )

    cv2.putText(
        output,
        f"Ratio: {activity_ratio:.4f}",
        (10, 130),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 200, 0),
        2
    )

    bar_ratio = min(activity_ratio / output_bar_max_ratio, 1.0)
    bar_width = int(bar_ratio * 200)

    cv2.rectangle(output, (10, 150), (10 + bar_width, 170), (0, 255, 0), -1)
    cv2.rectangle(output, (10, 150), (210, 170), (255, 255, 255), 2)

    return output
    

def main():
    config = load_config()

    mode = config.get("mode", "demo")  # demo / record
    show_window = config.get("show_window", True)
    show_fps = config.get("show_fps", True)
    output_bar_max_ratio = config.get("output_bar_max_ratio", 0.25)

    frame_queue = mp.Queue(maxsize=5)
    result_queue = mp.Queue(maxsize=5)
    record_queue = mp.Queue(maxsize=5)
    meta_queue = mp.Queue(maxsize=1)

    p1 = mp.Process(target=capture_process, args=(frame_queue, meta_queue, config))
    p2 = mp.Process(target=process_process, args=(frame_queue, result_queue, record_queue, config))
    p3 = mp.Process(target=record_process, args=(record_queue, meta_queue, config))

    p1.start()
    p2.start()
    p3.start()

    prev_time = time.time()

    try:
        while True:
            try:
                result = result_queue.get(timeout=0.1)
            except queue.Empty:
                result = None

            if result is None:
                # 下游收到 sentinel，結束主迴圈
                if not p2.is_alive() and result_queue.empty():
                    break
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break
                continue

            frame, edge_count, activity, activity_ratio = result

            current_time = time.time()
            fps = 1 / (current_time - prev_time) if current_time != prev_time else 0.0
            prev_time = current_time

            display_output = draw_overlay(
                frame=frame,
                fps=fps,
                edge_count=edge_count,
                activity=activity,
                activity_ratio=activity_ratio,
                show_fps=show_fps,
                output_bar_max_ratio=output_bar_max_ratio
            )

            if show_window:
                cv2.imshow("Result", display_output)

            if mode == "record" and not show_window:
                key = cv2.waitKey(1) & 0xFF
            else:
                key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                break

    except KeyboardInterrupt:
        print("Ctrl+C detected, shutting down...")

    finally:
        for proc in (p1, p2, p3):
            if proc.is_alive():
                proc.terminate()

        for proc in (p1, p2, p3):
            proc.join()

        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()