# Neural-Geolocated Disaster Splatting (3D NeRF Backend)

This is the production-ready backend repository for the **Neural-Geolocated Disaster Splatting** system. It is designed to act as an asynchronous spatial AI backend that ingests smartphone videos and georeferenced metadata, processes the imagery into 3D Gaussian Splats, and exposes geospatial query APIs optimized for a **Flutter** 3D mobile client.

---

## 🏗️ Project Architecture & Layout

The project uses a highly modular Python/FastAPI structure:

```
├── app/
│   ├── api/
│   │   ├── endpoints/
│   │   │   ├── jobs.py          # Stage 2: Video upload & training queue progress
│   │   │   └── splats.py        # Stage 1 & 3: Metadata, direct uploads, & GeoJSON search
│   │   └── __init__.py          # API Routers consolidation
│   ├── services/
│   │   ├── geometry.py          # WGS84 Geodetic to Cartesian (ECEF / ENU) transforms
│   │   ├── storage.py           # Local / Cloud multipart binary storage
│   │   └── __init__.py          # Services registry
│   ├── config.py                # Pydantic environment configurations
│   ├── database.py              # SQLAlchemy DB session & connection factory
│   ├── models.py                # DB Models: SplatCapture & ProcessingJob
│   ├── schemas.py               # Pydantic validation & GeoJSON serializers
│   ├── tasks.py                 # Keyframe extraction (OpenCV) & reconstruction pipeline
│   ├── main.py                  # Server bootstrap & premium Control Panel dashboard
│   └── __init__.py              # Package init
├── tests/
│   ├── conftest.py              # Test database engine & client dependency overrides
│   └── test_api.py              # Integration tests for direct splats, search, & video uploads
├── Dockerfile                   # Multi-stage production container configuration
├── docker-compose.yml           # Backend, Redis, Celery worker, and PostGIS compose stack
├── requirements.txt             # Python dependency packages
├── .env.example                 # Template for environment settings
└── README.md                    # This document
```

---

## 🚀 Dev Setup & Immediate Running

To verify and run this backend on your local environment:

### 1. Set Up Virtual Environment (Local Dev)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Automated Integration Tests
Verify that database schemas build, APIs serialize correctly, and geospatial searches math out flawlessly:
```bash
pytest -v
```

### 3. Start the Web Server
Launch the FastAPI development server:
```bash
uvicorn app.main:app --reload
```
Once booted, visit:
- **Control Panel Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/) - A stunning dark-mode GUI showing active splats.
- **Interactive Swagger OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) - Test requests and download models dynamically.

---

## 🛠️ 3-Stage Development Guidelines (For Claude Opus 4.7 / Next Agents)

Follow these directions to expand this scaffolded backend structure into production:

### 📍 Stage 1: Direct Splat Ingestion (Completed Foundation)
- **Status**: Ready.
- **Endpoint**: `POST /api/v1/splats/` registers WGS84 GPS (latitude, longitude, altitude) metadata with spatial coordinates, pitch/yaw/roll orientation matrix, and scale attributes.
- **Endpoint**: `POST /api/v1/splats/{id}/upload-asset` accepts direct `.ply` or `.splat` files, saves them, and flips the capture status to `completed`.
- **How to stream**: FastAPI serves the static files out of `static/splats/`. Uvicorn supports Range Requests out-of-the-box, allowing the 3D rendering client to chunk-stream file packets dynamically.

### 🎥 Stage 2: Video Pre-processing & Reconstruction Integration
- **Status**: Core scaffolding and pre-processing pipeline completed.
- **Task Orchestration**: Look at [app/tasks.py](file:///home/shri/.gitbuilds/disaster_gaussian_splatting/app/tasks.py). It implements a real keyframe selection system:
  1. Opens the uploaded video clip using **OpenCV** (`cv2.VideoCapture`).
  2. Extracts frames at specified time increments.
  3. Computes the **Laplacian variance** of each image to measure blurriness. If the frame is sharp (`variance > threshold`), it saves it; if blurry (camera shaking, fast motion), it discards it to prevent reconstruction artifacts!
  4. Compresses selected keyframes into a zip bundle to prepare for cloud ingestion.
- **Action Item for Next Agent**:
  - Integrate Luma AI API in the tasks worker. Replace the simulation loop in `execute_reconstruction_pipeline` with a POST call to Luma's `/captures` endpoint to create a training run, upload the zip archive, and poll `GET /captures/{id}` until the training state reaches `completed`.
  - Once complete, download the `.ply` or `.splat` file URL, save it locally (or to S3), and update `SplatCapture.file_url`.

### 📱 Stage 3: Flutter Client Integration & Scaling
- **Status**: Coordinate systems and GeoJSON serializers fully ready.
- **GeoJSON Searches**: Flutter map libraries (like `flutter_map` or Mapbox) require standard GeoJSON inputs to render markers. Use `GET /api/v1/splats/search/geojson?lat=27.7&lon=85.3&radius_km=10` to get a structured GeoJSON `FeatureCollection` containing all available disaster splats in the area, along with their orientation/scale metadata in the property fields.
- **3D Coordinate Projections**: When placing standard 3D point clouds on maps, standard floating-point numbers can lose precision (causing coordinate jitter) on large global coordinate frames (like ECEF).
  - Look at [app/services/geometry.py](file:///home/shri/.gitbuilds/disaster_gaussian_splatting/app/services/geometry.py). It implements geodetic conversion systems:
    - `wgs84_to_ecef(...)`: Converts WGS84 to Earth-Centered Earth-Fixed XYZ Cartesian coordinates.
    - `wgs84_to_enu(...)`: Converts target coordinates to local **East-North-Up (ENU)** plane tangent vectors relative to a reference coordinate. Provide the reference origin point to the Flutter engine to draw the 3D model accurately with high float precision.
- **Client Client-Side Generation**: Since the FastAPI endpoints are strictly typed with Pydantic, you can run a Flutter-side CLI command (e.g. using `openapi-generator`) pointing directly to `http://127.0.0.1:8000/openapi.json` to generate all REST client classes and JSON models in Dart automatically.

---

## 🐳 Running with Production Docker Compose
To run a complete high-availability cluster utilizing PostgreSQL/PostGIS, Redis, and a dedicated Celery task worker, spin up Docker Compose:
```bash
docker-compose up --build
```
This automatically initiates:
- PostGIS DB serving on `5432` with built-in spatial index support.
- Redis server serving on `6379` broker.
- Asynchronous Celery task processor listening for video frame queues.
- Web API serving on `8000`.
