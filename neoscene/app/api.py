"""FastAPI HTTP API for Neoscene scene generation.

This module exposes HTTP endpoints for generating MuJoCo scenes from
natural language descriptions.

Run with:
    uvicorn neoscene.app.api:app --reload
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from neoscene.backends.session_manager import SceneSessionManager
from neoscene.core.errors import (
    AssetNotFoundError,
    LLMError,
    NeosceneError,
)
from neoscene.core.llm_client import GeminiClient
from neoscene.core.logging_config import get_logger, setup_logging
from neoscene.core.scene_agent import SceneAgent, SceneGenerationError
from neoscene.core.scene_tools import list_assets_by_category, search_assets
from neoscene.exporters.mjcf_exporter import scene_to_mjcf

# Setup logging
setup_logging()
logger = get_logger(__name__)

# =============================================================================
# FastAPI App Configuration
# =============================================================================

app = FastAPI(
    title="Neoscene API",
    description="Text-to-scene generator for MuJoCo simulations",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(NeosceneError)
async def neoscene_exception_handler(request: Request, exc: NeosceneError):
    """Handle all Neoscene-specific errors with friendly messages."""
    logger.warning(f"NeosceneError: {exc.message}")

    status_code = 400
    if isinstance(exc, LLMError):
        status_code = 502  # Bad Gateway for LLM errors
    elif isinstance(exc, AssetNotFoundError):
        status_code = 404

    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors with truncated messages."""
    error_msg = str(exc)[:500]  # Truncate long error messages
    logger.error(f"Unexpected error: {error_msg}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": f"An unexpected error occurred: {error_msg}",
        },
    )


# =============================================================================
# Initialize Singletons
# =============================================================================

# Get the assets path relative to this file
asset_root = Path(__file__).resolve().parents[1] / "assets"

# Create singleton instances
session_manager = SceneSessionManager(asset_root)
llm = GeminiClient.from_default_config()
agent = SceneAgent(session_manager.catalog, llm)

logger.info(f"Initialized with {len(session_manager.catalog)} assets from {asset_root}")


# =============================================================================
# Request/Response Models
# =============================================================================


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    session_id: str
    user_message: str
    assistant_message: str
    scene_spec: Optional[Dict[str, Any]] = None
    scene_summary: Dict[str, Any]


class GenerateSceneRequest(BaseModel):
    """Request body for scene generation."""

    prompt: str = Field(
        ...,
        description="Natural language description of the desired scene",
        min_length=3,
        examples=["An orchard with a tractor and some crates"],
    )
    include_mjcf: bool = Field(
        default=True,
        description="Whether to include the MJCF XML in the response",
    )
    repair_on_error: bool = Field(
        default=True,
        description="Whether to attempt repair if initial generation fails",
    )


class GenerateSceneResponse(BaseModel):
    """Response body for scene generation."""

    id: str = Field(description="Unique identifier for this generation")
    scene_spec: Dict[str, Any] = Field(description="The generated SceneSpec as JSON")
    mjcf_xml: Optional[str] = Field(
        default=None,
        description="The generated MJCF XML string (if requested)",
    )
    created_at: str = Field(description="ISO timestamp of generation")


class AssetInfo(BaseModel):
    """Information about an asset."""

    asset_id: str
    name: str
    category: str
    tags: List[str]


class AssetListResponse(BaseModel):
    """Response for asset listing."""

    assets: List[AssetInfo]
    total: int


class SearchAssetsRequest(BaseModel):
    """Request for asset search."""

    query: str = Field(..., min_length=1)
    category: Optional[str] = Field(default=None)
    limit: int = Field(default=10, ge=1, le=50)


class ErrorResponse(BaseModel):
    """Error response body."""

    error: str
    details: Optional[List[str]] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    llm_configured: bool
    llm_available: bool
    assets_loaded: int


# =============================================================================
# Chat Endpoint
# =============================================================================


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(req: ChatRequest):
    """Chat-driven scene generation with memory.

    Send a natural language message to create or modify a scene.
    The MuJoCo viewer will automatically launch/restart with the new scene.

    - First message: Creates a new scene from scratch.
    - Subsequent messages: Edits the existing scene incrementally.
    - Say "start over" or "new scene" to reset.
    """
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Get or create session
    session = session_manager.get_or_create_session(req.session_id)

    logger.info(f"[{session.session_id}] Chat: '{message[:100]}...'")

    # Use update_scene_spec for incremental editing
    try:
        spec = agent.update_scene_spec(session.last_scene, message)
    except SceneGenerationError as e:
        raise HTTPException(status_code=500, detail=f"Failed to update scene: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update scene: {e}")

    # Update viewer
    session_manager.update_scene(session, spec)

    # Prepare assistant message (short summary)
    summary = session_manager.describe_scene(session)
    assistant_msg = (
        f"Updated scene '{summary.get('scene_name', 'unnamed')}'. "
        f"{summary.get('object_count', 0)} object(s), "
        f"{summary.get('camera_count', 0)} camera(s), "
        f"environment: {summary.get('environment_asset_id', 'unknown')}."
    )

    logger.info(f"[{session.session_id}] Generated: {summary.get('scene_name')}")

    return ChatResponse(
        session_id=session.session_id,
        user_message=req.message,
        assistant_message=assistant_msg,
        scene_spec=spec.model_dump(),
        scene_summary=summary,
    )


# =============================================================================
# Static File Serving
# =============================================================================


@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def index():
    """Serve the chat UI."""
    html_path = static_dir / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Neoscene API</h1><p>Static files not found. Visit <a href='/docs'>/docs</a></p>")


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check the health of the API and its dependencies."""
    return HealthResponse(
        status="healthy",
        llm_configured=llm.is_configured,
        llm_available=llm.is_available,
        assets_loaded=len(session_manager.catalog),
    )


@app.get("/api", tags=["System"])
async def api_info():
    """API information endpoint."""
    return {
        "name": "Neoscene API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "chat": "/chat",
    }


@app.post(
    "/generate_scene",
    response_model=GenerateSceneResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Asset not found"},
        500: {"model": ErrorResponse, "description": "Generation failed"},
        502: {"model": ErrorResponse, "description": "LLM error"},
    },
    tags=["Scene Generation"],
)
async def generate_scene(req: GenerateSceneRequest):
    """Generate a MuJoCo scene from a natural language description.

    This endpoint takes a text prompt describing a scene and returns:
    - A SceneSpec JSON object describing the scene
    - Optionally, the MJCF XML that can be loaded by MuJoCo

    The LLM will select appropriate assets from the catalog and
    position them according to the description.
    """
    import uuid
    from datetime import datetime

    logger.info(f"Generating scene for prompt: '{req.prompt[:100]}...'")

    # Generate the scene spec (exceptions will be caught by handlers)
    if req.repair_on_error:
        spec = agent.generate_and_repair(req.prompt)
    else:
        spec = agent.generate_scene_spec(req.prompt)

    logger.info(
        f"Scene generated: name='{spec.name}', "
        f"env='{spec.environment.asset_id}', "
        f"objects={len(spec.objects)}"
    )

    # Generate MJCF if requested
    mjcf_xml = None
    if req.include_mjcf:
        mjcf_xml = scene_to_mjcf(spec, session_manager.catalog)
        logger.debug(f"MJCF generated: {len(mjcf_xml)} bytes")

    return GenerateSceneResponse(
        id=str(uuid.uuid4()),
        scene_spec=spec.model_dump(),
        mjcf_xml=mjcf_xml,
        created_at=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/assets", response_model=AssetListResponse, tags=["Assets"])
async def list_assets(category: Optional[str] = None):
    """List all available assets, optionally filtered by category.

    Categories:
    - environment: Base scenes (terrains, rooms)
    - robot: Controllable agents (vehicles, arms)
    - prop: Static objects (crates, trees)
    - sensor: Cameras and sensors
    """
    assets = list_assets_by_category(session_manager.catalog, category=category)

    return AssetListResponse(
        assets=[AssetInfo(**a) for a in assets],
        total=len(assets),
    )


@app.post("/assets/search", response_model=AssetListResponse, tags=["Assets"])
async def search_assets_endpoint(req: SearchAssetsRequest):
    """Search for assets matching a query.

    The search looks at asset names, tags, and semantic information.
    """
    results = search_assets(
        session_manager.catalog,
        query=req.query,
        category=req.category,
        limit=req.limit,
    )

    return AssetListResponse(
        assets=[AssetInfo(**a) for a in results],
        total=len(results),
    )


# =============================================================================
# Sensor & Camera Endpoints
# =============================================================================


@app.get("/sensors/{session_id}", tags=["Telemetry"])
async def get_sensors(session_id: str):
    """Get latest sensor values for a session.
    
    Returns sensor data from the headless simulation worker.
    Poll this endpoint at ~2Hz for live telemetry.
    """
    result = session_manager.get_sensors(session_id)
    return JSONResponse(result)


@app.get("/camera/{session_id}", tags=["Telemetry"])
async def get_camera(session_id: str):
    """Get latest camera image for a session.
    
    Returns a JPEG image from the first camera in the scene.
    Poll this endpoint at ~1Hz for live camera feed.
    Returns 204 No Content if no image is available.
    """
    image = session_manager.get_camera_image(session_id)
    
    if image is None:
        return Response(status_code=204)
    
    # Encode numpy image as JPEG
    try:
        import cv2
        # Convert RGB to BGR for cv2 encoding
        if len(image.shape) == 3 and image.shape[2] == 3:
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            image_bgr = image
        _, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return Response(
            content=buf.tobytes(),
            media_type="image/jpeg",
        )
    except ImportError:
        # cv2 not available, try PIL
        try:
            from PIL import Image
            import io
            pil_image = Image.fromarray(image)
            buf = io.BytesIO()
            pil_image.save(buf, format="JPEG", quality=80)
            return Response(
                content=buf.getvalue(),
                media_type="image/jpeg",
            )
        except ImportError:
            return Response(status_code=204)


class ControlInput(BaseModel):
    """Control input for vehicle."""
    throttle: float = Field(0.0, ge=-1.0, le=1.0, description="Throttle: -1 (reverse) to 1 (forward)")
    steering: float = Field(0.0, ge=-1.0, le=1.0, description="Steering: -1 (left) to 1 (right)")


@app.post("/control/{session_id}", tags=["Telemetry"])
async def set_control(session_id: str, control: ControlInput):
    """Set control inputs for a session's vehicle.
    
    Use this endpoint to drive robots/vehicles in the simulation.
    Call continuously while key is held (e.g., every 100ms).
    
    - throttle: -1.0 (full reverse) to 1.0 (full forward)
    - steering: -1.0 (left) to 1.0 (right)
    """
    session = session_manager.get_or_create_session(session_id)
    worker = session.sim_worker
    
    if worker is None:
        return JSONResponse({"ok": False, "error": "No simulation running"}, status_code=200)
    
    worker.set_controls(control.throttle, control.steering)
    return JSONResponse({"ok": True, "throttle": control.throttle, "steering": control.steering})
