from fastapi import FastAPI, HTTPException, Path
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from typing import Dict
from db.db import get_collection
from db.models import IntersectionModel, UpdateIntersectionModel

server = FastAPI()

intersections = get_collection("intersections")

@server.post("/intersections")
async def create_intersection(data: IntersectionModel):
    # Convert Pydantic model to dict for MongoDB
    doc = data.model_dump(by_alias=True, exclude={"id"})
    result = await intersections.insert_one(doc)
    return {"id": str(result.inserted_id)}


@server.patch("/intersections/{id}")
async def update_intersection(
    id: str = Path(..., description="MongoDB ObjectId of the intersection"),
    update_data: UpdateIntersectionModel = None
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    current_doc = await intersections.find_one({"_id": ObjectId(id)})
    if not current_doc:
        raise HTTPException(status_code=404, detail="Intersection not found")

    update_dict = randomize_traffic_params(current_doc)
    print("Randomized traffic params:", update_dict)

    # Update top-level fields
    for key, value in update_dict.items():
        if key != "routes":
            current_doc[key] = value

    # Update nested routes
    if "routes" in update_dict:
        for dir_key, route_update in update_dict["routes"].items():
            if dir_key in current_doc["routes"]:
                current_doc["routes"][dir_key].update(route_update)
            else:
                current_doc["routes"][dir_key] = route_update

    await intersections.update_one({"_id": ObjectId(id)}, {"$set": current_doc})

    # Convert ObjectId to string for JSON response
    current_doc["_id"] = str(current_doc["_id"])

    return {"updated_intersection": current_doc}
