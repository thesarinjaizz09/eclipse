import asyncio
import cv2
import numpy as np
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription
import pygame
import sim  # your sim.py
import threading
from aiohttp import web
import av
import aiohttp_cors
from queue import Empty
import time
import logging
import json
import os
import random
import simv2
import simUser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamer")

DATA_FILE = "sim_data.txt"  # write each update here
DATA_FILE2 = "sim_datav2.txt"  # write each update here
DATA_FILE3 = "sim_datav3.txt"  # write each update here

sim_thread, simv2_thread, simv3_thread = None, None, None
stop_sim_flag, stop_simv2_flag, stop_simv3_flag = False, False, False


def write_sim_data():
    """Background thread that writes sim variables to a text file continuously."""
    while True:
        if sim.SIM_STARTED:
            try:
                # Convert signal objects to dicts
                signals_dict = [s.to_dict() for s in sim.signals]
                
                total_crossed = sum(lane['crossed'] for lane in sim.LANE_STATE.values())
                total_spawned = sum(lane['spawned'] for lane in sim.LANE_STATE.values())
                throughput_percent = (total_crossed / total_spawned) * 100

                # Small random fluctuations
                ingress = sim.SPAWN_INTERVAL + random.uniform(-2, 2)         # +/- 2 seconds
                velocity = sim.AVG_SPEED + random.uniform(-0.3, 0.3)         # +/- 0.3 m/s
                latency = sim.SECONDS_PER_VEHICLE + random.uniform(-2, 2)    # +/- 2 seconds

                # Minimal random percentage for alerts & offences
                alerts = round(random.uniform(0, 5), 2)       # 0% to 5%
                offences = round(random.uniform(0, 5), 2)     # 0% to 5%

                payload = {
                    "timestamp": time.time(),
                    "lane_state": dict(sim.LANE_STATE),
                    "time_elapsed": sim.time_elapsed,
                    "current_green": sim.current_green,
                    "current_yellow": sim.current_yellow,
                    "simultaneous_green": sim.simultaneous_green,
                    "spawn_counts": sim.SPAWN_COUNTS,
                    "signal_state": signals_dict,
                    "ingress": round(ingress, 2),
                    "velocity": round(velocity, 2),
                    "latency": round(latency, 2),
                    "alerts": alerts,
                    "offences": offences,
                    "vehicles": sim.VEHICLE_LIST,
                    "throughput": round(throughput_percent, 2)
                }

                # Write JSON string to file (overwrite each time)
                with open(DATA_FILE, "w") as f:
                    f.write(json.dumps(payload, indent=2))

            except Exception as e:
                logger.exception("[ERROR] Failed to write sim data: %s", e)

        time.sleep(0.2)  # adjust interval

def write_sim_datav2():
    """Background thread that writes sim variables to a text file continuously."""
    while True:
        if simv2.SIM_STARTED:
            try:
                total_crossed = 0
                total_spawned = 0

                for inter in simv2.INTERSECTIONS:  # or just `sim` if single intersection
                    for direction in ["up", "down", "left", "right"]:
                        # sum crossed per lane
                        total_crossed += sum(inter.vehicles[direction]['crossed'].values())
                        # sum spawned per lane
                        total_spawned += sum(inter.SPAWN_COUNTS[direction].values())

                # Avoid division by zero
                throughput_percent = (total_crossed / total_spawned * 100) if total_spawned else 0

                # Small random fluctuations
                ingress = simv2.SPAWN_INTERVAL + random.uniform(-2, 2)         # +/- 2 seconds
                velocity = simv2.AVG_SPEED + random.uniform(-0.3, 0.3)         # +/- 0.3 m/s
                latency = simv2.SECONDS_PER_VEHICLE + random.uniform(-2, 2)    # +/- 2 seconds

                # Minimal random percentage for alerts & offences
                alerts = round(random.uniform(0, 5), 2)       # 0% to 5%
                offences = round(random.uniform(0, 5), 2)     # 0% to 5%

                payload = {
                    "timestamp": time.time(),
                    "time_elapsed": simv2.time_elapsed,
                    "ingress": round(ingress, 2),
                    "velocity": round(velocity, 2),
                    "latency": round(latency, 2),
                    "alerts": alerts,
                    "offences": offences,
                    "vehicles": simv2.VEHICLE_LIST,
                    "throughput": round(throughput_percent, 2),
                    "intersections": [inter.to_dict() for inter in simv2.INTERSECTIONS],
                    "spawned": total_spawned,
                    "crossed": total_crossed
                }

                # Write JSON string to file (overwrite each time)
                with open(DATA_FILE2, "w") as f:
                    f.write(json.dumps(payload, indent=2))

            except Exception as e:
                logger.exception("[ERROR] Failed to write sim data: %s", e)

        time.sleep(0.2)  # adjust interval

def write_sim_datav3():
    """Background thread that writes sim variables to a text file continuously."""
    while True:
        if simUser.SIM_STARTED:
            try:
                # Convert signal objects to dicts
                signals_dict = [s.to_dict() for s in simUser.signals]
                
                total_crossed = sum(lane['crossed'] for lane in simUser.LANE_STATE.values())
                total_spawned = sum(lane['spawned'] for lane in simUser.LANE_STATE.values())
                throughput_percent = (total_crossed / total_spawned) * 100

                # Small random fluctuations
                ingress = simUser.SPAWN_INTERVAL + random.uniform(-2, 2)         # +/- 2 seconds
                velocity = simUser.AVG_SPEED + random.uniform(-0.3, 0.3)         # +/- 0.3 m/s
                latency = simUser.SECONDS_PER_VEHICLE + random.uniform(-2, 2)    # +/- 2 seconds

                # Minimal random percentage for alerts & offences
                alerts = round(random.uniform(0, 5), 2)       # 0% to 5%
                offences = round(random.uniform(0, 5), 2)     # 0% to 5%

                payload = {
                    "timestamp": time.time(),
                    "suggestion": simUser.SUGGESTION,
                    "lane_state": dict(simUser.LANE_STATE),
                    "time_elapsed": simUser.time_elapsed,
                    "current_green": simUser.current_green,
                    "current_yellow": simUser.current_yellow,
                    "simultaneous_green": simUser.simultaneous_green,
                    "spawn_counts": simUser.SPAWN_COUNTS,
                    "signal_state": signals_dict,
                    "ingress": round(ingress, 2),
                    "velocity": round(velocity, 2),
                    "latency": round(latency, 2),
                    "alerts": alerts,
                    "offences": offences,
                    "vehicles": simUser.VEHICLE_LIST,
                    "throughput": round(throughput_percent, 2)
                }

                # Write JSON string to file (overwrite each time)
                with open(DATA_FILE3, "w") as f:
                    f.write(json.dumps(payload, indent=2))

            except Exception as e:
                logger.exception("[ERROR] Failed to write sim user data: %s", e)

        time.sleep(0.2)  # adjust interval

async def set_user_override(request):
    direction = request.headers.get("Direction")
    print(direction)
    if not direction:
        return web.json_response({"error": "Missing Direction header"}, status=400)

    # sanitize: allow only valid directions
    valid_dirs = ["up", "down", "left", "right"]
    if direction.lower() not in valid_dirs:
        return web.json_response({"error": "Invalid direction"}, status=400)

    simUser.USER_OVERRIDE_DIR = direction.lower()
    logger.info(f"[INFO] User override set to {direction.lower()}")

    return web.json_response({"status": f"Override set to {direction.lower()}"})


class PygameVideoTrack(VideoStreamTrack):
    """WebRTC video track from Pygame surface."""

    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame_surface = None
        try:
            while True:
                frame_surface = sim.FRAME_QUEUE.get_nowait()
        except Empty:
            pass

        if frame_surface is None:
            frame_surface = pygame.Surface((sim.SCREEN_WIDTH, sim.SCREEN_HEIGHT))

        frame = pygame.surfarray.array3d(frame_surface)
        frame = np.transpose(frame, (1, 0, 2))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame
class PygameVideoTrackv2(VideoStreamTrack):
    """WebRTC video track from Pygame surface."""

    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame_surface = None
        try:
            while True:
                frame_surface = simv2.FRAME_QUEUE.get_nowait()
        except Empty:
            pass

        if frame_surface is None:
            frame_surface = pygame.Surface((simv2.SCREEN_WIDTH, simv2.SCREEN_HEIGHT))

        frame = pygame.surfarray.array3d(frame_surface)
        frame = np.transpose(frame, (1, 0, 2))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame
class PygameVideoTrackv3(VideoStreamTrack):
    """WebRTC video track from Pygame surface."""

    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame_surface = None
        try:
            while True:
                frame_surface = simUser.FRAME_QUEUE.get_nowait()
        except Empty:
            pass

        if frame_surface is None:
            frame_surface = pygame.Surface((simUser.SCREEN_WIDTH, simUser.SCREEN_HEIGHT))

        frame = pygame.surfarray.array3d(frame_surface)
        frame = np.transpose(frame, (1, 0, 2))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


async def offer(request):
    logger.info("[INFO] Received offer from %s", request.remote)
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["offer"]["sdp"], type=params["offer"]["type"])

    pc = RTCPeerConnection()
    sender = pc.addTrack(PygameVideoTrack())

    await pc.setRemoteDescription(offer)

    try:
        try:
            params_obj = sender.getParameters()
        except Exception:
            params_obj = sender.get_parameters()

        encodings = [{"maxBitrate": 600_000, "maxFramerate": 30}]
        if isinstance(params_obj, dict):
            params_obj["encodings"] = encodings
        else:
            setattr(params_obj, "encodings", encodings)

        try:
            await sender.setParameters(params_obj)
        except Exception:
            try:
                await sender.set_parameters(params_obj)
            except Exception:
                logger.info("[INFO] Couldn't apply encoding params")
    except Exception as e:
        logger.info("[INFO] Could not set sender encoding parameters: %s", e)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response(
        {"answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}}
    )

async def offerv2(request):
    logger.info("[INFO] Received offer from %s", request.remote)
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["offer"]["sdp"], type=params["offer"]["type"])

    pc = RTCPeerConnection()
    sender = pc.addTrack(PygameVideoTrackv2())

    await pc.setRemoteDescription(offer)

    try:
        try:
            params_obj = sender.getParameters()
        except Exception:
            params_obj = sender.get_parameters()

        encodings = [{"maxBitrate": 600_000, "maxFramerate": 30}]
        if isinstance(params_obj, dict):
            params_obj["encodings"] = encodings
        else:
            setattr(params_obj, "encodings", encodings)

        try:
            await sender.setParameters(params_obj)
        except Exception:
            try:
                await sender.set_parameters(params_obj)
            except Exception:
                logger.info("[INFO] Couldn't apply encoding params")
    except Exception as e:
        logger.info("[INFO] Could not set sender encoding parameters: %s", e)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response(
        {"answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}}
    )

async def offerv3(request):
    logger.info("[INFO] Received offer from %s", request.remote)
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["offer"]["sdp"], type=params["offer"]["type"])

    pc = RTCPeerConnection()
    sender = pc.addTrack(PygameVideoTrackv3())

    await pc.setRemoteDescription(offer)

    try:
        try:
            params_obj = sender.getParameters()
        except Exception:
            params_obj = sender.get_parameters()

        encodings = [{"maxBitrate": 600_000, "maxFramerate": 30}]
        if isinstance(params_obj, dict):
            params_obj["encodings"] = encodings
        else:
            setattr(params_obj, "encodings", encodings)

        try:
            await sender.setParameters(params_obj)
        except Exception:
            try:
                await sender.set_parameters(params_obj)
            except Exception:
                logger.info("[INFO] Couldn't apply encoding params")
    except Exception as e:
        logger.info("[INFO] Could not set sender encoding parameters: %s", e)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response(
        {"answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}}
    )


# async def start_sim(request):
#     if sim.SIM_STARTED:
#         return web.json_response({"status": "already running"})

#     def run_sim():
#         logger.info("[INFO] Starting simulation...")
#         sim.main()

#     threading.Thread(target=run_sim, daemon=True).start()
#     return web.json_response({"status": "Simulation started"})

# async def get_sim_data(request):
#     """Serve the latest sim data from the text file as JSON."""
#     if not os.path.exists(DATA_FILE):
#         return web.json_response({"status": "no data yet"}, status=404)
#     try:
#         with open(DATA_FILE, "r") as f:
#             text = f.read()
#             data = json.loads(text)
#         return web.json_response(data)
#     except Exception as e:
#         logger.exception("[ERROR] Failed to read sim data: %s", e)
#         return web.json_response({"status": "error"}, status=500)
    
    
# async def start_simv2(request):
#     if simv2.SIM_STARTED:
#         return web.json_response({"status": "already running"})

#     def run_sim():
#         logger.info("[INFO] Starting simulation...")
#         simv2.main()

#     threading.Thread(target=run_sim, daemon=True).start()
#     return web.json_response({"status": "Simulation started"})

# async def get_sim_datav2(request):
#     """Serve the latest sim data from the text file as JSON."""
#     if not os.path.exists(DATA_FILE2):
#         return web.json_response({"status": "no data yet"}, status=404)
#     try:
#         with open(DATA_FILE2, "r") as f:
#             text = f.read()
#             data = json.loads(text)
#         return web.json_response(data)
#     except Exception as e:
#         logger.exception("[ERROR] Failed to read sim v2 data: %s", e)
#         return web.json_response({"status": "error"}, status=500)


# async def start_simv3(request):
#     if sim.SIM_STARTED:
#         return web.json_response({"status": "already running"})

#     def run_sim():
#         logger.info("[INFO] Starting simulation...")
#         simUser.main()

#     threading.Thread(target=run_sim, daemon=True).start()
#     return web.json_response({"status": "Simulation started"})

# async def get_sim_datav3(request):
#     """Serve the latest sim data from the text file as JSON."""
#     if not os.path.exists(DATA_FILE3):
#         return web.json_response({"status": "no data yet"}, status=404)
#     try:
#         with open(DATA_FILE3, "r") as f:
#             text = f.read()
#             data = json.loads(text)
#         return web.json_response(data)
#     except Exception as e:
#         logger.exception("[ERROR] Failed to read sim user data: %s", e)
#         return web.json_response({"status": "error"}, status=500)
    
async def start_sim(request):
    global sim_thread, stop_sim_flag
    if sim_thread and sim_thread.is_alive():
        return web.json_response({"status": "already running"})

    stop_sim_flag = False
    sim.STOP_FLAG = False
    

    def run():
        logger.info("[INFO] Starting simulation v1...")
        sim.main(stop_flag=lambda: stop_sim_flag)

    sim_thread = threading.Thread(target=run, daemon=True)
    sim_thread.start()
    return web.json_response({"status": "Simulation started"})


async def stop_sim(request):
    global stop_sim_flag
    if not sim_thread or not sim_thread.is_alive():
        return web.json_response({"status": "not running"})
    sim.stop_event.set()
    logger.info("[INFO] Stop requested for simulation v1")
    return web.json_response({"status": "Simulation stop requested"})


async def get_sim_data(request):
    if not os.path.exists(DATA_FILE):
        return web.json_response({"status": "no data yet"}, status=404)
    try:
        with open(DATA_FILE, "r") as f:
            return web.json_response(json.load(f))
    except Exception as e:
        logger.exception("[ERROR] Failed to read sim data: %s", e)
        return web.json_response({"status": "error"}, status=500)
    
    
async def start_simv2(request):
    global simv2_thread, stop_simv2_flag
    if simv2_thread and simv2_thread.is_alive():
        return web.json_response({"status": "already running"})

    stop_simv2_flag = False
    simv2.STOP_FLAG = False
    
    def run():
        logger.info("[INFO] Starting simulation v2...")
        simv2.main(stop_flag=lambda: stop_simv2_flag)

    simv2_thread = threading.Thread(target=run, daemon=True)
    simv2_thread.start()
    return web.json_response({"status": "Simulation v2 started"})


async def stop_simv2(request):
    global stop_simv2_flag
    if not simv2_thread or not simv2_thread.is_alive():
        return web.json_response({"status": "not running"})
    simv2.STOP_FLAG = True
    logger.info("[INFO] Stop requested for simulation v2")
    return web.json_response({"status": "Simulation v2 stop requested"})


async def get_sim_datav2(request):
    if not os.path.exists(DATA_FILE2):
        return web.json_response({"status": "no data yet"}, status=404)
    try:
        with open(DATA_FILE2, "r") as f:
            return web.json_response(json.load(f))
    except Exception as e:
        logger.exception("[ERROR] Failed to read sim v2 data: %s", e)
        return web.json_response({"status": "error"}, status=500)



async def start_simv3(request):
    global simv3_thread, stop_simv3_flag
    if simv3_thread and simv3_thread.is_alive():
        return web.json_response({"status": "already running"})

    stop_simv3_flag = False
    simUser.STOP_FLAG = False

    def run():
        logger.info("[INFO] Starting simulation v3...")
        simUser.main(stop_flag=lambda: stop_simv3_flag)

    simv3_thread = threading.Thread(target=run, daemon=True)
    simv3_thread.start()
    return web.json_response({"status": "Simulation v3 started"})


async def stop_simv3(request):
    global stop_simv3_flag
    if not simv3_thread or not simv3_thread.is_alive():
        return web.json_response({"status": "not running"})
    simUser.STOP_FLAG = True
    logger.info("[INFO] Stop requested for simulation v3")
    return web.json_response({"status": "Simulation v3 stop requested"})


async def get_sim_datav3(request):
    if not os.path.exists(DATA_FILE3):
        return web.json_response({"status": "no data yet"}, status=404)
    try:
        with open(DATA_FILE3, "r") as f:
            return web.json_response(json.load(f))
    except Exception as e:
        logger.exception("[ERROR] Failed to read sim v3 data: %s", e)
        return web.json_response({"status": "error"}, status=500)


import aiohttp_cors
from aiohttp import web



def run_web_app():
    app = web.Application()
    app.router.add_post("/offer", offer)
    app.router.add_post("/offerv2", offerv2)
    app.router.add_post("/offerv3", offerv3)
    app.router.add_get("/start-sim", start_sim)
    app.router.add_get("/start-simv2", start_simv2)
    app.router.add_get("/start-simv3", start_simv3)
    app.router.add_get("/stop-sim", stop_sim)
    app.router.add_get("/stop-simv2",stop_simv2)
    app.router.add_get("/stop-simv3",stop_simv3)
    app.router.add_get("/meta.json", get_sim_data)
    app.router.add_get("/metav2.json", get_sim_datav2)
    app.router.add_get("/metav3.json", get_sim_datav3)
    app.router.add_get("/set-signal", set_user_override)

    # Setup CORS
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "http://localhost:5173": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        },
    )

    # Apply CORS to all routes explicitly
    for route in list(app.router.routes()):
        cors.add(route)
        
    # cors.add(start_route)
    # cors.add(start_routev2)

    logger.info("[INFO] Web server running at http://0.0.0.0:8080")
    web.run_app(app, host="0.0.0.0", port=8080)



if __name__ == "__main__":
    threading.Thread(target=write_sim_data, daemon=True).start()
    threading.Thread(target=write_sim_datav2, daemon=True).start()
    threading.Thread(target=write_sim_datav3, daemon=True).start()
    run_web_app()
