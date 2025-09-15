import random
import asyncio
from bson import ObjectId
from db.db import get_collection
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

console = Console()

laneConstant = 40
activeDuration = 5
intersectionId = "68c088aacbffff0096e9446c"

def print_signal_table(signal_data):
    """
    signal_data = [
        {"name": "Opposite", "status": "active", "duration": 10, "incoming": 20, "outgoing": 15},
        ...
    ]
    """
    table = Table(title="Traffic Signal Analytics", show_lines=True)

    table.add_column("Signal", style="cyan bold", justify="center")
    table.add_column("Status", style="green", justify="center")
    table.add_column("Duration (s)", style="magenta", justify="center")
    table.add_column("Incoming Vehicles", style="yellow", justify="center")
    table.add_column("Outgoing Vehicles", style="red", justify="center")

    for row in signal_data:
        status_style = "green" if row["status"] == "active" else "red"
        table.add_row(
            row["name"],
            f"[{status_style}]{row['status']}[/{status_style}]",
            str(row["duration"]),
            str(row["incoming"]),
            str(row["outgoing"])
        )

    return table # Extra space below the table

def randomize_traffic_params(intersection: dict) -> dict:
    """
    Updates the 'incomingParameters' and 'outgoingParameters' for each route (N, S, E, W)
    with random integers between 1 and 40.
    """
    for direction in ['N', 'S', 'E', 'W']:
        if direction in intersection['routes']:
            intersection['routes'][direction]['incomingParameters'] = random.randint(1, 40)
            intersection['routes'][direction]['outgoingParameters'] = random.randint(1, 40)
    return intersection

def calculate_signal(lane, incoming, outgoing):
    if lane - (incoming + outgoing) >= 0:
        return incoming, "active"
    elif outgoing < lane:
        vehicles_can_pass = lane - outgoing
        if vehicles_can_pass >= 5:
            return vehicles_can_pass, "active"
    return 0, "inactive"

intersections = get_collection("intersections")

async def update_intersection_traffic_count():
    if not ObjectId.is_valid(intersectionId):
        print("Invalid ObjectId")
        return

    current_doc = await intersections.find_one({"_id": ObjectId(intersectionId)})
    if not current_doc:
        print("Intersection not found")
        return

    update_dict = randomize_traffic_params(current_doc)

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

    await intersections.update_one({"_id": ObjectId(intersectionId)}, {"$set": current_doc})

    # Convert ObjectId to string for JSON response
    current_doc["_id"] = str(current_doc["_id"])
    return current_doc
    
async def live_countdown(duration, panel_text, signal_table):
    """
    Shows a live countdown in seconds with a panel and signal table.
    """
    with Live(refresh_per_second=2) as live:
        for remaining in range(duration, 0, -1):
            panel = Panel(
                f"{panel_text}\n[bold blue]Countdown:[/bold blue] {remaining} seconds remaining",
                expand=False
            )
            layout = Table.grid()
            layout.add_row(panel)
            layout.add_row(signal_table)
            live.update(layout)
            await asyncio.sleep(1)

async def main():
    elapsed_time = 0
    while True:
        current_doc = await update_intersection_traffic_count()
        activeRoute = current_doc.get("activeRouteDirection", "O")
        
        routes = current_doc.get("routes", {})

        maxIncomingParamsRoute = max([
            {"direction": dir_key, "incoming": route["incomingParameters"], "outgoing": route["outgoingParameters"]}
            for dir_key, route in routes.items()
            if dir_key != activeRoute
        ], key=lambda x: x["incoming"])
        
        routeToBeActivatedDirection = maxIncomingParamsRoute["direction"]
        routeToBeActivatedIncoming = maxIncomingParamsRoute["incoming"]
        routeToBeActivatedOutgoing = maxIncomingParamsRoute["outgoing"]
        
        routeToBeActivatedLeftIncoming = routeToBeActivatedIncoming * 0.25
        routeToBeActivatedRightIncoming = routeToBeActivatedIncoming * 0.25
        routeToBeActivatedOppositeIncoming = routeToBeActivatedIncoming * 0.50
        
        routeToBeActivated = routes.get(routeToBeActivatedDirection, {})
        
        oppositeRoute = routes.get(routeToBeActivated.get('oppositeRouteDirection', 'O'), {})
        oppositeRouteOutgoing = oppositeRoute.get("outgoingParameters", 0)
        
        leftRoute = routes.get(routeToBeActivated.get('leftTurnRouteDirection', 'O'), {})
        leftRouteOutgoing = leftRoute.get("outgoingParameters", 0)
        
        rightRoute = routes.get(routeToBeActivated.get('rightTurnRouteDirection', 'O'), {})
        rightRouteOutgoing = rightRoute.get("outgoingParameters", 0)
        simultaneousRouteLeftIncoming = rightRoute.get("incomingParameters", 0) * 0.25
                
        signal_mapping = {
        "Opposite": (routeToBeActivatedOppositeIncoming, oppositeRouteOutgoing),
        "Left": (routeToBeActivatedLeftIncoming, leftRouteOutgoing),
        "Right": (routeToBeActivatedRightIncoming, rightRouteOutgoing),
        "Simultaneous": (simultaneousRouteLeftIncoming, routeToBeActivatedOutgoing)
        }

        signal_data = []
        for name, (incoming, outgoing) in signal_mapping.items():
            duration, status = calculate_signal(laneConstant, incoming, outgoing)
            signal_data.append({
                "name": name, "status": status, "duration": duration,
                "incoming": incoming, "outgoing": outgoing
            })


        max_signal = max(signal_data, key=lambda x: x["duration"])
        activeDuration = max_signal["duration"]
        panel_text = (
            f"[bold cyan]Traffic Intersection Update[/bold cyan]\n"
            f"Elapsed Time: [blue]{elapsed_time}s[/blue]\n"
            f"Route to be activated: [yellow]{routeToBeActivatedDirection}[/yellow]\n"
            f"Incoming: [green]{routeToBeActivatedIncoming}[/green], Outgoing: [red]{routeToBeActivatedOutgoing}[/red]\n"
            f"Active Signal Duration: [magenta]{activeDuration}[/magenta] seconds"
        )
        signal_table =print_signal_table(signal_data)
        console.print("-" * 60 + "\n")

        await live_countdown(int(activeDuration), panel_text, signal_table)
        elapsed_time += activeDuration

if __name__ == "__main__":
    asyncio.run(main())