# Modu-Catholic Crawler

This directory contains the data collection pipeline for the Modu-Catholic project.

## Architecture

The pipeline follows an **ETL (Extract, Transform, Load)** pattern:

1.  **Collector (Hybrid API):** `crawler.py`
    *   **API**: Fetches church lists from `catholicapi.catholic.or.kr`.
    *   **Mobile Web**: Parses detail pages (`maria.catholic.or.kr/mobile`) for mass times.
    *   Saves data to `data/catholic_data.json`.
2.  **Loader:** `firebase_uploader.py`
    *   Uploads data to **Firestore** (`catholic_churches` collection).
    *   Supports Batch Upload and Single Hot-fix modes.

## Ethical Crawling Strategy
*   **Rate Limiting**: Random sleep (1-3s) between requests.
*   **Retry Logic**: 3 retries with delay for failed requests.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: Playwright is no longer strictly required for the crawler but might be useful for future expansions.*

2. Firebase Setup:
   - Place `serviceAccountKey.json` in this `crawler/` directory.

## Usage

### 1. Run the Crawler
**Search Mode:**
```bash
python crawler.py --keyword "명동"
```

**Bulk Mode:**
```bash
python crawler.py --max_pages 5
```

### 2. Upload to Firebase
**Batch Upload (All):**
```bash
python firebase_uploader.py
```

**Hot-fix (Single):**
```bash
python firebase_uploader.py --name "명동성당"
```
