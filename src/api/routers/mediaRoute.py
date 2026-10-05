import os
from typing import List
from fastapi import APIRouter, Query, UploadFile, File
from fastapi.responses import FileResponse

from sqlalchemy import select


from src.api.core.operation import listRecords
from src.api.models.mediaModel import Media, MediaRead
from src.api.core.operation.media import MEDIA_DIR, delete_media_items, uploadImage
from src.api.core.dependencies import GetSession, ListQueryParams
from src.api.core.response import api_response, raiseExceptions

from src.api.core import requireSignin, requireAdmin

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/create")
async def upload_images(
    session: GetSession,
    user: requireSignin,
    files: List[UploadFile] = File(...),
    thumbnail: bool = False,
):
    records = []  # collect both old and new
    message = "Images uploaded successfully"

    # 🔑 Save files to disk + build file_info dicts
    saved_files = await uploadImage(files, thumbnail)

    for file_info in saved_files:
        existing_media = session.scalar(
            select(Media).where(Media.filename == file_info["filename"])
        )
        print(existing_media)

        if existing_media:
            # ✅ Update existing record
            existing_media.extension = file_info["extension"]
            existing_media.original = file_info["original"]
            existing_media.size_mb = file_info["size_mb"]
            existing_media.thumbnail = file_info.get("thumbnail")
            existing_media.media_type = "image"
            session.add(existing_media)
            records.append(existing_media)
        else:
            # ✅ Create new record
            media = Media(
                filename=file_info["filename"],
                extension=file_info["extension"],
                original=file_info["original"],
                size_mb=file_info["size_mb"],
                thumbnail=file_info.get("thumbnail"),
                media_type="image",
            )
            session.add(media)
            session.flush()  # ensures ID assigned
            records.append(media)

    session.commit()

    return api_response(
        200,
        message,
        [MediaRead.model_validate(m) for m in records],
    )


# ✅ READ (single)
@router.get("/read/{id}", response_model=MediaRead)
def get(id: int, session: GetSession):
    read = session.get(Media, id)
    raiseExceptions((read, 404, "Media not found"))

    return api_response(200, "Media Found", MediaRead.model_validate(read))


@router.get("/list", response_model=list[MediaRead])
def list(user: requireAdmin, query_params: ListQueryParams):
    query_params = vars(query_params)
    searchFields = ["media_type"]

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=Media,
        Schema=MediaRead,
    )


# ----------------------------
# Get single image (GET)
# ----------------------------
@router.get("/{filename}")
async def get_image(filename: str):

    file_path = os.path.join(MEDIA_DIR, filename)

    if not os.path.isfile(file_path):
        return api_response(404, "File not found")
    return FileResponse(file_path)


# ----------------------------
# Delete Images Ids (DELETE)
# ----------------------------
@router.delete("/delete-by-ids")
async def delete_by_ids(
    session: GetSession,
    # user: requireAdmin,
    ids: List[int] = Query(
        ..., description="IDs of media to delete"
    ),  # e.g. /media/delete-by-ids?ids=1&ids=2&ids=3
):
    response = delete_media_items(session=session, ids=ids)
    if len(response["deleted"]) == 0:
        return api_response(400, response["message"])
    session.commit()

    return api_response(
        200,
        "Media deleted successfully",
        response["deleted"],
    )


@router.delete("/delete-by-filenames")
async def delete_by_filenames(
    session: GetSession,
    user: requireAdmin,
    filenames: List[str] = Query(
        ...,
        description="Filenames of media to delete. Example: ?filenames=1.webp&filenames=2.webp",
    ),
):
    response = delete_media_items(
        session=session,
        filenames=filenames,
    )
    if len(response["deleted"]) == 0:
        return api_response(400, response["message"])

    session.commit()

    return api_response(
        200,
        "Deleted successfully",
        response["deleted"],
    )
