# streamer.py
import asyncio, cv2, numpy as np
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole
import pygame
import simulation  # import your simulation.py
import threading
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiohttp import web
import av
import aiohttp_cors



class PygameVideoTrack(VideoStreamTrack):
    """
    Video track that pulls frames from the simulation's Pygame surface
    """
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        # Grab the latest frame from Pygame
        if not simulation.FRAME_QUEUE.empty():
            frame_surface = simulation.FRAME_QUEUE.get()
        else:
            # If no frame, send black frame
            frame_surface = pygame.Surface((simulation.SCREEN_WIDTH, simulation.SCREEN_HEIGHT))

        # Convert Pygame surface -> BGR
        frame = pygame.surfarray.array3d(frame_surface)
        
        frame = np.transpose(frame, (1, 0, 2))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        print("[INFO] Sending frame", frame.shape)
        import av  # PyAV
        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

async def run_pc():
    pc = RTCPeerConnection()
    pc.addTrack(PygameVideoTrack())
    print("WebRTC peer ready. Connect with your client.")
    # Keep the process alive
    await asyncio.Event().wait()
    
async def offer(request):
    print(f"[INFO] Received offer from {request.remote}")
    params = await request.json()
    offer = RTCSessionDescription(
        sdp=params["offer"]["sdp"], type=params["offer"]["type"]
    )
    pc = RTCPeerConnection()
    pc.addTrack(PygameVideoTrack())
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.json_response({"answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}})

def run_web_app():
    app = web.Application()
    app.router.add_post("/offer", offer)

    # Setup CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })

    # Apply CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)

    print("[INFO] Web server running at http://0.0.0.0:8080")
    web.run_app(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    # Start simulation in a separate thread
    threading.Thread(target=run_web_app, daemon=True).start()
    simulation.main()
