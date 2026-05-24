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
