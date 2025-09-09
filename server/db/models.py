from typing import Optional, Dict, Literal
from pydantic import BaseModel
from bson import ObjectId

# Handle MongoDB ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


# ---------------- ROUTE MODEL ----------------
class RouteModel(BaseModel):
    routeId: str
    direction: str
    connectedIntersectionId: str
    outgoingParameters: int
    incomingParameters: int
    status: str  # e.g., "active" or "inactive"
    oppositeRouteDirection: str
    simultaneousRouteDirection: str
    leftTurnRouteDirection: str
    rightTurnRouteDirection: str
    activeDuration: int


# ---------------- INTERSECTION MODEL ----------------
class IntersectionModel(BaseModel):
    intersectionId: str
    eastIntersectionId: Optional[str]
    westIntersectionId: Optional[str]
    northIntersectionId: Optional[str]
    southIntersectionId: Optional[str]
    activeRouteDirection: Literal['N', 'S', 'E', 'W', 'O']

    # Routes are a dictionary with keys like "N", "S", "E", "W"
    routes: Dict[str, RouteModel]

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
        arbitrary_types_allowed = True


# ---------------- UPDATE ROUTE MODEL ----------------
class UpdateRouteModel(BaseModel):
    routeId: Optional[str] = None
    direction: Optional[str] = None
    connectedIntersectionId: Optional[str] = None
    outgoingParameters: Optional[int] = None
    incomingParameters: Optional[int] = None
    status: Optional[str] = None
    oppositeRouteDirection: Optional[str] = None
    simultaneousRouteDirection: Optional[str] = None
    leftTurnRouteDirection: Optional[str] = None
    rightTurnRouteDirection: Optional[str] = None
    activeDuration: Optional[int] = None


# ---------------- UPDATE INTERSECTION MODEL ----------------
class UpdateIntersectionModel(BaseModel):
    intersectionId: Optional[str] = None
    eastIntersectionId: Optional[str] = None
    westIntersectionId: Optional[str] = None
    northIntersectionId: Optional[str] = None
    southIntersectionId: Optional[str] = None
    activeRouteDirection: Optional[Literal['N','S','E','W','O']] = None

    # Routes dictionary with optional Route updates
    routes: Optional[Dict[str, UpdateRouteModel]] = None

    class Config:
        arbitrary_types_allowed = True