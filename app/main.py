from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import engine, Base, get_db
from app.models import SplatCapture
from app.api import api_router

# 1. Create database schema tables on startup
# (Ideal for SQLite instant runs; production environments should use Alembic migrations)
Base.metadata.create_all(bind=engine)

# 2. Initialize FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Geospatial AI backend for 3D Gaussian Splatting / NeRF Disaster Mapping",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 3. Enable CORS for cross-platform Flutter clients (iOS, Android, Web, Desktop)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Mount Static directories for streaming large .splat / .ply model files
# Mounting `/static` serves locally uploaded videos, ply, and splat assets directly.
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# 5. Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", response_class=HTMLResponse, tags=["health"])
def index_dashboard(db: Session = Depends(get_db)):
    """
    A stunning, dark-mode status panel dashboard showing active 3D disaster splat files 
    registered on the server, showing current geospatial metadata and processing health.
    """
    captures = db.query(SplatCapture).order_by(SplatCapture.created_at.desc()).all()
    
    # Calculate counters
    total = len(captures)
    completed = sum(1 for c in captures if c.status == "completed")
    processing = sum(1 for c in captures if c.status == "processing")
    failed = sum(1 for c in captures if c.status == "failed")
    
    # Render premium HTML dashboard
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{settings.PROJECT_NAME} - Control Panel</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-gradient: linear-gradient(135deg, #0d0e15 0%, #151828 100%);
                --card-bg: rgba(26, 29, 50, 0.6);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-primary: #f3f4f6;
                --text-secondary: #9ca3af;
                --accent-primary: #6366f1; /* Purple/Indigo */
                --accent-success: #10b981; /* Emerald */
                --accent-warning: #f59e0b; /* Amber */
                --accent-danger: #ef4444;  /* Red */
            }}
            
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            
            body {{
                font-family: 'Outfit', sans-serif;
                background: var(--bg-gradient);
                color: var(--text-primary);
                min-height: 100vh;
                padding: 2rem;
                line-height: 1.6;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            
            header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 3rem;
                border-bottom: 1px solid var(--card-border);
                padding-bottom: 1.5rem;
            }}
            
            .logo {{
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }}
            
            .logo-icon {{
                width: 2.5rem;
                height: 2.5rem;
                background: linear-gradient(135deg, var(--accent-primary) 0%, #a855f7 100%);
                border-radius: 0.75rem;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                color: white;
                box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
            }}
            
            h1 {{
                font-size: 1.75rem;
                font-weight: 700;
                background: linear-gradient(to right, #ffffff, #a5b4fc);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            
            .docs-btn {{
                background: rgba(99, 102, 241, 0.1);
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.3);
                padding: 0.6rem 1.2rem;
                border-radius: 0.5rem;
                text-decoration: none;
                font-weight: 600;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }}
            
            .docs-btn:hover {{
                background: var(--accent-primary);
                color: white;
                box-shadow: 0 0 15px rgba(99, 102, 241, 0.3);
                transform: translateY(-2px);
            }}
            
            /* Stats Bar */
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 1.5rem;
                margin-bottom: 3rem;
            }}
            
            .stat-card {{
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                backdrop-filter: blur(12px);
                border-radius: 1rem;
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
                position: relative;
                overflow: hidden;
            }}
            
            .stat-card::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 4px;
                height: 100%;
            }}
            
            .stat-card.total::before {{ background-color: var(--accent-primary); }}
            .stat-card.completed::before {{ background-color: var(--accent-success); }}
            .stat-card.processing::before {{ background-color: var(--accent-warning); }}
            .stat-card.failed::before {{ background-color: var(--accent-danger); }}
            
            .stat-value {{
                font-size: 2.5rem;
                font-weight: 700;
                margin-top: 0.5rem;
            }}
            
            .stat-label {{
                color: var(--text-secondary);
                text-transform: uppercase;
                font-size: 0.75rem;
                letter-spacing: 0.1em;
                font-weight: 600;
            }}
            
            /* Splat Table list */
            .splat-list-section {{
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                backdrop-filter: blur(12px);
                border-radius: 1.25rem;
                padding: 2rem;
                box-shadow: 0 10px 30px rgba(0,0,0,0.25);
            }}
            
            .section-title {{
                font-size: 1.25rem;
                margin-bottom: 1.5rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                text-align: left;
            }}
            
            th {{
                color: var(--text-secondary);
                font-size: 0.85rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                padding: 1rem;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            
            td {{
                padding: 1.25rem 1rem;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
                font-size: 0.95rem;
            }}
            
            tr:last-child td {{
                border-bottom: none;
            }}
            
            .badge {{
                display: inline-flex;
                align-items: center;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: capitalize;
            }}
            
            .badge.completed {{
                background: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.2);
            }}
            
            .badge.processing {{
                background: rgba(245, 158, 11, 0.15);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.2);
            }}
            
            .badge.failed {{
                background: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.2);
            }}
            
            .badge.pending {{
                background: rgba(156, 163, 175, 0.15);
                color: #d1d5db;
                border: 1px solid rgba(156, 163, 175, 0.2);
            }}
            
            .badge-severity {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: var(--text-primary);
            }}
            
            .badge-severity.critical {{
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.4);
                color: #f87171;
            }}
            
            .badge-severity.high {{
                background: rgba(245, 158, 11, 0.2);
                border: 1px solid rgba(245, 158, 11, 0.4);
                color: #fbbf24;
            }}
            
            .coordinates {{
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.8rem;
                color: #a5b4fc;
            }}
            
            .empty-state {{
                text-align: center;
                padding: 4rem 2rem;
                color: var(--text-secondary);
            }}
            
            .empty-icon {{
                font-size: 3rem;
                margin-bottom: 1rem;
                opacity: 0.5;
            }}
            
            .file-link {{
                color: #818cf8;
                text-decoration: none;
                font-size: 0.9rem;
                transition: color 0.2s;
            }}
            
            .file-link:hover {{
                color: #a5b4fc;
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="logo">
                    <div class="logo-icon">3D</div>
                    <div>
                        <h1>{settings.PROJECT_NAME}</h1>
                        <p style="color: var(--text-secondary); font-size: 0.85rem;">Geolocated AI 3D Reconstruction Console</p>
                    </div>
                </div>
                <a href="/docs" class="docs-btn" target="_blank">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                    Interactive OpenAPI API Docs
                </a>
            </header>
            
            <div class="stats-grid">
                <div class="stat-card total">
                    <span class="stat-label">Total Captures</span>
                    <span class="stat-value">{total}</span>
                </div>
                <div class="stat-card completed">
                    <span class="stat-label">Active Splats</span>
                    <span class="stat-value">{completed}</span>
                </div>
                <div class="stat-card processing">
                    <span class="stat-label">In Training Queue</span>
                    <span class="stat-value">{processing}</span>
                </div>
                <div class="stat-card failed">
                    <span class="stat-label">Failed Tasks</span>
                    <span class="stat-value">{failed}</span>
                </div>
            </div>
            
            <div class="splat-list-section">
                <h2 class="section-title">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-primary);"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    Geolocated Disaster 3D Splat Assets
                </h2>
                
                {f"""
                <table>
                    <thead>
                        <tr>
                            <th>Location / Title</th>
                            <th>Disaster Type</th>
                            <th>Severity</th>
                            <th>Coordinates (Lon, Lat)</th>
                            <th>Status</th>
                            <th>3D Splat File (.splat)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f'''
                        <tr>
                            <td>
                                <strong>{c.title}</strong>
                                <div style="font-size: 0.8rem; color: var(--text-secondary); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    {c.description or "No description provided."}
                                </div>
                            </td>
                            <td><span class="badge" style="background: rgba(99, 102, 241, 0.1); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.2);">{c.disaster_type}</span></td>
                            <td><span class="badge badge-severity {c.severity.lower()}">{c.severity}</span></td>
                            <td><span class="coordinates">{c.longitude:.5f}, {c.latitude:.5f}</span></td>
                            <td><span class="badge {c.status.lower()}">{c.status}</span></td>
                            <td>
                                {f'<a href="{c.file_url}" class="file-link" download>Download Splat File</a>' if c.file_url else '<span style="color: var(--text-secondary); font-size: 0.85rem;">Generating...</span>'}
                            </td>
                        </tr>
                        ''' for c in captures)}
                    </tbody>
                </table>
                """ if captures else f"""
                <div class="empty-state">
                    <div class="empty-icon">🛰️</div>
                    <h3>No Splats Registered</h3>
                    <p style="margin-top: 0.5rem; font-size: 0.9rem;">Submit geolocated 3D image tags or upload a video clip via the API client to trigger 3D reconstruction.</p>
                </div>
                """}
            </div>
        </div>
    </body>
    </html>
    """
    return html_content
