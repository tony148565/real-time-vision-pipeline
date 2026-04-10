# 即時影像處理系統（Multiprocessing Vision Pipeline）

## 專案概述
本專案實作一個基於 Python 與 OpenCV 的即時影像處理系統，  
透過 multiprocessing 建立多程序（multi-process）架構，實現影片擷取、影像分析與結果輸出的解耦（decoupling）。

系統以固定視角交通影片為例，透過可配置的 ROI（Region of Interest）區域，進行邊緣偵測與簡易車流活動分析。

本專案重點在於展示即時影像處理 pipeline 與多程序架構設計，  
而非追求高精度車流辨識模型。

---

## 系統架構

本系統採用 Producer–Consumer Pipeline 設計：
```
[Capture Process] → [Processing Process] → [Display / Record]
```

- **Capture Process**
  - 讀取影片來源
  - 控制 FPS 並推送影格至佇列（Queue）

- **Processing Process**
  - 進行灰階轉換與 Canny 邊緣偵測
  - 套用梯形 ROI（模擬道路透視）
  - 計算 ROI 內邊緣密度（Edge Density）
  - 判斷車流活動等級（LOW / MEDIUM / HIGH）

- **Record Process**
  - 將處理後影像輸出為影片檔（output.mp4）

- **Main Process**
  - 顯示結果畫面（含 FPS、統計資訊）
  - 控制整體流程與中斷機制

---

## 功能特色

- 多程序架構（multiprocessing）
- Queue-based IPC（程序間通訊）
- 即時影像處理（real-time processing）
- 可配置 ROI（支援不同場景調整）
- 基於比例的活動判定（提升跨影片穩定性）
- 支援影片輸出（record mode）

---
## 技術重點

- 使用 multiprocessing 建立非阻塞影像處理流程
- 採用 Queue 實現程序間解耦（IPC）
- 建立可擴展的影像處理 `pipeline（capture → process → output）`

---
## 設定方式（config.json）

系統透過 `config.json` 控制主要參數：

```json
{
  "video_source": "test.mp4",
  "roi_points_ratio": [
    [0.12, 1.0],
    [0.30, 0.55],
    [0.60, 0.55],
    [0.85, 1.0]
  ],
  "low_ratio": 0.05,
  "high_ratio": 0.15
}
```
### 說明
- `roi_points_ratio`: 使用相對座標（0~1），可適應不同解析度影片
- `low_ratio` / `high_ratio`: 根據 ROI 內邊緣密度比例判斷車流狀態

---
## 執行方式
```
python main.py
```

---
## 設計說明
1. 多程序設計（Multiprocessing）
	將影片擷取與影像處理分離，避免單一流程阻塞，提升即時性。

2. 解耦架構（Decoupling）
	透過 Queue 作為資料傳遞媒介，使各模組獨立運作，方便擴充與替換。

3. ROI 設計（Perspective-aware ROI）
	採用梯形區域模擬道路透視，提升分析的場景合理性。
	
4. 比例化判定（Normalized Metric）
	使用「邊緣數量 / ROI 面積」作為指標，避免不同影片解析度造成偏差。

---
## 限制與未來改進
- 目前 ROI 為手動設定（未自動化）
- 車流判定基於邊緣密度，未使用物件偵測（如 YOLO）
- 尚未加入追蹤（tracking）或跨幀分析

---
## 未來可擴充方向：
- 自動 ROI 偵測（lane detection / segmentation）
- 物件偵測與車輛計數
- Web UI 或即時串流（streaming）

---

## DEMO
![demo](./demo.gif)


### Demo 影片來源
本專案使用 YouTube 上 [公開交通監視影片](https://www.youtube.com/watch?v=PJ5xXXcfuTc) 作為示範資料，
僅用於技術展示用途，版權屬原始內容提供者所有。

