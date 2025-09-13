# streamer.py
import asyncio
import cv2
import numpy as np
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole
import pygame
import simulation  # import your simulation.py
import threading
from aiohttp import web
import av
import aiohttp_cors
from queue import Empty
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamer")


class PygameVideoTrack(VideoStreamTrack):
    """
    Video track that pulls the *latest* frame from the simulation's Pygame surface.
    To minimize latency we drain the FRAME_QUEUE so we always send the freshest frame
    instead of backing up older frames.
    """
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        # --- Grab the freshest frame from the queue (drain older frames) ---
        frame_surface = None
        try:
            # Keep popping until queue empty; last popped frame is the freshest
            while True:
                frame_surface = simulation.FRAME_QUEUE.get_nowait()
        except Empty:
            pass

        if frame_surface is None:
            # No frames available -> send a black frame of the same size
            frame_surface = pygame.Surface((simulation.SCREEN_WIDTH, simulation.SCREEN_HEIGHT))

        # Convert Pygame surface -> NumPy array -> BGR
        frame = pygame.surfarray.array3d(frame_surface)
        frame = np.transpose(frame, (1, 0, 2))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Debug log: shape + approximate timestamp
        logger.debug("[INFO] Sending frame %s @ %.3f", frame.shape, time.time())

        # Wrap in PyAV VideoFrame and preserve pts/time_base from next_timestamp
        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


async def run_pc():
    pc = RTCPeerConnection()
    pc.addTrack(PygameVideoTrack())
    logger.info("WebRTC peer ready. Connect with your client.")
    # Keep the process alive
    await asyncio.Event().wait()


async def offer(request):
    logger.info("[INFO] Received offer from %s", request.remote)
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["offer"]["sdp"], type=params["offer"]["type"])

    pc = RTCPeerConnection()
    # Add track (we will attempt to set sender params afterwards)
    sender = pc.addTrack(PygameVideoTrack())

    await pc.setRemoteDescription(offer)

    # --- Attempt to set low-latency encoding parameters on the sender ---
    # This helps reduce encoder buffering and controls bitrate/framerate.
    try:
        # aiortc's Python API may differ by version: try the most common names and ignore failures.
        try:
            params_obj = sender.getParameters()  # JS-like API if available
        except Exception:
            params_obj = sender.get_parameters()  # snake_case fallback

        # Attempt to assign encodings. This object type may be dict-like or a class instance
        # depending on aiortc version; do best-effort assignment.
        encodings = [{"maxBitrate": 600_000, "maxFramerate": 30}]
        # if params_obj is dict-like
        if isinstance(params_obj, dict):
            params_obj["encodings"] = encodings
        else:
            # object with attributes
            setattr(params_obj, "encodings", encodings)

        # Now try to set them back on the sender
        try:
            await sender.setParameters(params_obj)
        except Exception:
            try:
                await sender.set_parameters(params_obj)
            except Exception:
                logger.info("[INFO] Couldn't call sender.setParameters - skipping server-side encoding tweak.")
    except Exception as e:
        # Not fatal — just log and continue. Some aiortc builds don't support setParameters.
        logger.info("[INFO] Could not set sender encoding parameters: %s", e)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response(
        {"answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}}
    )


def run_web_app():
    app = web.Application()
    app.router.add_post("/offer", offer)

    # Setup CORS
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True, expose_headers="*", allow_headers="*"
            )
        },
    )

    # Apply CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)

    logger.info("[INFO] Web server running at http://0.0.0.0:8080")
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    # Start web app in a separate thread so simulation.main() can run in main thread (as your original)
    threading.Thread(target=run_web_app, daemon=True).start()
    simulation.main()
