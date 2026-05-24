import io


def test_create_splat_metadata(client):
    """
    Test registering new disaster geospatial metadata coordinates (Stage 1).
    """
    response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Kathmandu Mudslide Area A",
            "description": "Critical road blockage caused by heavy rainfall mudslide.",
            "disaster_type": "landslide",
            "severity": "critical",
            "latitude": 27.7172,
            "longitude": 85.3240,
            "altitude": 1400.0,
            "roll": 0.0,
            "pitch": 15.5,
            "yaw": 180.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "scale_z": 1.2
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Kathmandu Mudslide Area A"
    assert data["status"] == "pending"
    assert "id" in data
    assert data["latitude"] == 27.7172
    assert data["longitude"] == 85.3240


def test_direct_splat_upload(client):
    """
    Test direct ingestion upload of pre-processed .splat file (Stage 1 MVP).
    """
    # 1. Register capture
    reg_response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Immediate Splat Ingestion",
            "disaster_type": "flood",
            "severity": "medium",
            "latitude": 27.7172,
            "longitude": 85.3240
        }
    )
    capture_id = reg_response.json()["id"]
    
    # 2. Direct upload asset
    file_content = b"MOCK_BINARY_PLY_OR_SPLAT_DATA"
    file_io = io.BytesIO(file_content)
    
    upload_response = client.post(
        f"/api/v1/splats/{capture_id}/upload-asset",
        files={"file": ("capture.splat", file_io, "application/octet-stream")}
    )
    
    assert upload_response.status_code == 200
    data = upload_response.json()
    assert data["status"] == "completed"
    assert data["file_url"].endswith(".splat")


def test_geospatial_radius_search(client):
    """
    Test geolocated search queries and coordinate distance matching (Stage 1 & 3).
    """
    # Register Capture A - close to center (approx 1 km)
    client.post(
        "/api/v1/splats/",
        json={
            "title": "Capture A (Close)",
            "disaster_type": "wildfire",
            "severity": "high",
            "latitude": 27.7100,  # Near center (27.7000)
            "longitude": 85.3000, # Near center (85.3000)
            "status": "completed" # Mock completed status directly
        }
    )
    
    # Force state to completed by uploading mock file to A
    # Let's just retrieve the capture id and upload
    captures = client.get("/api/v1/splats/search?lat=27.7000&lon=85.3000&radius_km=10")
    
    # Register Capture B - far away (approx 60 km)
    client.post(
        "/api/v1/splats/",
        json={
            "title": "Capture B (Far)",
            "disaster_type": "wildfire",
            "severity": "high",
            "latitude": 28.2000,  # ~60km away
            "longitude": 85.3000
        }
    )
    
    # Since search only queries status = "completed", let's upload a dummy file to A
    # Get all splats and complete A
    all_res = client.post(
        "/api/v1/splats/",
        json={
            "title": "Completed Splat",
            "disaster_type": "wildfire",
            "severity": "high",
            "latitude": 27.7050,
            "longitude": 85.3050
        }
    )
    cap_id = all_res.json()["id"]
    client.post(
        f"/api/v1/splats/{cap_id}/upload-asset",
        files={"file": ("completed.splat", io.BytesIO(b"data"), "application/octet-stream")}
    )
    
    # Search within 10 km
    search_response = client.get("/api/v1/splats/search?lat=27.7000&lon=85.3000&radius_km=10")
    assert search_response.status_code == 200
    results = search_response.json()
    
    # Should only return Completed Splat (since B is 60km away, and first A wasn't completed via file upload)
    assert len(results) == 1
    assert results[0]["title"] == "Completed Splat"
    
    # Verify GeoJSON radius endpoint (Stage 3)
    geojson_response = client.get("/api/v1/splats/search/geojson?lat=27.7000&lon=85.3000&radius_km=10")
    assert geojson_response.status_code == 200
    geojson = geojson_response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    feature = geojson["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert feature["properties"]["title"] == "Completed Splat"


def test_video_job_pipeline_trigger(client):
    """
    Test uploading a video segment and registering a background reconstruction task (Stage 2).
    """
    video_content = b"FAKE_VIDEO_MP4_HEADER_BLOCK_DATA"
    video_io = io.BytesIO(video_content)
    
    response = client.post(
        "/api/v1/jobs/upload-video",
        data={
            "title": "Drone Flyover Damage Area C",
            "description": "High resolution drone mapping clip.",
            "disaster_type": "flood",
            "severity": "high",
            "latitude": 27.7172,
            "longitude": 85.3240,
            "altitude": 1350.0
        },
        files={"file": ("flyover.mp4", video_io, "video/mp4")}
    )
    
    assert response.status_code == 202
    job_data = response.json()
    assert job_data["progress"] == 0
    assert job_data["status_message"] == "Video uploaded successfully. Starting pipeline..."
    assert "id" in job_data
    
    # Query job progress status
    status_response = client.get(f"/api/v1/jobs/{job_data['id']}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["id"] == job_data["id"]


def test_index_dashboard(client):
    """
    Test GET / root dashboard endpoint returns stunning dark-mode status panel.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Neural-Geolocated Disaster Splatting" in response.text
    assert "Total Captures" in response.text


def test_create_splat_metadata_invalid(client):
    """
    Test validation of coordinate bounds on POST /api/v1/splats/.
    """
    # Invalid latitude (> 90)
    response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Invalid Lat",
            "disaster_type": "flood",
            "severity": "low",
            "latitude": 95.0,
            "longitude": 85.3240
        }
    )
    assert response.status_code == 422

    # Invalid longitude (< -180)
    response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Invalid Lon",
            "disaster_type": "flood",
            "severity": "low",
            "latitude": 27.7172,
            "longitude": -185.0
        }
    )
    assert response.status_code == 422


def test_upload_direct_splat_file_errors(client):
    """
    Test error paths for direct splat/ply asset upload.
    """
    # 1. Non-existent splat capture ID (expected 404)
    file_io = io.BytesIO(b"MOCK_DATA")
    response = client.post(
        "/api/v1/splats/non-existent-id-123/upload-asset",
        files={"file": ("capture.splat", file_io, "application/octet-stream")}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Splat metadata record not found"

    # 2. Valid splat ID but invalid file format (expected 400)
    # Register capture first
    reg_response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Capture with invalid file",
            "disaster_type": "flood",
            "severity": "medium",
            "latitude": 27.7172,
            "longitude": 85.3240
        }
    )
    capture_id = reg_response.json()["id"]

    file_io_txt = io.BytesIO(b"text file content")
    response_txt = client.post(
        f"/api/v1/splats/{capture_id}/upload-asset",
        files={"file": ("capture.txt", file_io_txt, "text/plain")}
    )
    assert response_txt.status_code == 400
    assert response_txt.json()["detail"] == "Invalid file format. Only .ply and .splat files are allowed"


def test_get_splat_details(client):
    """
    Test retrieving details of a specific Splat Capture (GET /api/v1/splats/{splat_id}).
    """
    # 1. Register a capture
    reg_response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Detail Retrieve Test",
            "disaster_type": "landslide",
            "severity": "critical",
            "latitude": 27.7172,
            "longitude": 85.3240
        }
    )
    capture_id = reg_response.json()["id"]

    # 2. Get capture details (expected 200)
    response = client.get(f"/api/v1/splats/{capture_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Detail Retrieve Test"
    assert data["id"] == capture_id

    # 3. Retrieve non-existent capture details (expected 404)
    response_404 = client.get("/api/v1/splats/invalid-uuid-999")
    assert response_404.status_code == 404
    assert response_404.json()["detail"] == "Splat capture not found"


def test_update_splat_metadata(client):
    """
    Test updating calibration tags or metadata (PATCH /api/v1/splats/{splat_id}).
    """
    # 1. Register a capture
    reg_response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Before Update Title",
            "description": "Old Description",
            "disaster_type": "landslide",
            "severity": "critical",
            "latitude": 27.7172,
            "longitude": 85.3240,
            "scale_x": 1.0
        }
    )
    capture_id = reg_response.json()["id"]

    # 2. Update metadata fields (expected 200)
    update_response = client.patch(
        f"/api/v1/splats/{capture_id}",
        json={
            "title": "After Update Title",
            "description": "New Description",
            "severity": "low",
            "scale_x": 2.5
        }
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "After Update Title"
    assert data["description"] == "New Description"
    assert data["severity"] == "low"
    assert data["scale_x"] == 2.5
    assert data["disaster_type"] == "landslide"  # remains unchanged

    # 3. Attempt update on non-existent splat ID (expected 404)
    response_404 = client.patch(
        "/api/v1/splats/non-existent-splat-id",
        json={"title": "Doesn't matter"}
    )
    assert response_404.status_code == 404
    assert response_404.json()["detail"] == "Splat capture not found"


def test_delete_splat_capture(client):
    """
    Test deleting a registered splat capture and database record (DELETE /api/v1/splats/{splat_id}).
    """
    # 1. Register capture
    reg_response = client.post(
        "/api/v1/splats/",
        json={
            "title": "Delete Test Splat",
            "disaster_type": "wildfire",
            "severity": "high",
            "latitude": 27.7172,
            "longitude": 85.3240
        }
    )
    capture_id = reg_response.json()["id"]

    # 2. Delete the record (expected 204)
    delete_response = client.delete(f"/api/v1/splats/{capture_id}")
    assert delete_response.status_code == 204

    # 3. Verify it is removed from the database (GET returns 404)
    get_response = client.get(f"/api/v1/splats/{capture_id}")
    assert get_response.status_code == 404

    # 4. Deleting a non-existent capture ID (expected 404)
    delete_response_404 = client.delete("/api/v1/splats/already-deleted-or-none")
    assert delete_response_404.status_code == 404
    assert delete_response_404.json()["detail"] == "Splat capture not found"


def test_upload_disaster_video_errors(client):
    """
    Test video upload error handling for invalid format on POST /api/v1/jobs/upload-video.
    """
    video_content = b"fake text data"
    video_io = io.BytesIO(video_content)

    response = client.post(
        "/api/v1/jobs/upload-video",
        data={
            "title": "Drone Clip",
            "disaster_type": "flood",
            "severity": "high",
            "latitude": 27.7172,
            "longitude": 85.3240
        },
        files={"file": ("flyover.txt", video_io, "text/plain")}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid video format. Supported formats: .mp4, .mov, .avi"


def test_get_job_status_errors(client):
    """
    Test querying job status for a non-existent job ID (GET /api/v1/jobs/{job_id}).
    """
    response = client.get("/api/v1/jobs/non-existent-job-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Processing job not found"


def test_get_job_by_capture(client):
    """
    Test querying reconstruction job associated with a specific capture ID (GET /api/v1/jobs/capture/{capture_id}).
    """
    # 1. Trigger valid video job pipeline upload
    video_content = b"FAKE_VIDEO_MP4"
    video_io = io.BytesIO(video_content)
    
    response = client.post(
        "/api/v1/jobs/upload-video",
        data={
            "title": "Capture for Job Retrieve Test",
            "disaster_type": "flood",
            "severity": "high",
            "latitude": 27.7172,
            "longitude": 85.3240
        },
        files={"file": ("flyover.mp4", video_io, "video/mp4")}
    )
    assert response.status_code == 202
    job_data = response.json()
    capture_id = job_data["capture_id"]
    job_id = job_data["id"]

    # 2. Get job by capture ID (expected 200)
    response_job = client.get(f"/api/v1/jobs/capture/{capture_id}")
    assert response_job.status_code == 200
    retrieved_job = response_job.json()
    assert retrieved_job["id"] == job_id
    assert retrieved_job["capture_id"] == capture_id

    # 3. Query job by non-existent/unassociated capture ID (expected 404)
    response_404 = client.get("/api/v1/jobs/capture/unassociated-capture-id-999")
    assert response_404.status_code == 404
    assert response_404.json()["detail"] == "No processing job found for this capture"

