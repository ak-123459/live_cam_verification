"""
Image Upload API
----------------
POST /images/upload  → accepts multiple images, returns their filenames
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import uvicorn

app = FastAPI( title="Image Upload API",
    description="Upload images and get back their filenames",
    version="1.0.0")

# ── Allowed image types ───────────────────────────────────────
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}



@app.post("/images/upload")
async def upload_images(
    files: List[UploadFile] = File(..., description="List of images to upload")
):
    """
    Upload multiple images and get back their filenames.

    - **files**: list of image files (jpg, png, webp)

    Returns list of uploaded image filenames.
    """

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    result = []

    for file in files:

        # ── Validate file type ────────────────────────────────
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"'{file.filename}' is not a valid image. Allowed: jpg, png, webp"
            )

        result.append(file.filename)

    return JSONResponse(content={
        "total"    : len(result),
        "images"   : result,
    })



# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("face_verification_api:app", host="0.0.0.0", port=8003, reload=True)