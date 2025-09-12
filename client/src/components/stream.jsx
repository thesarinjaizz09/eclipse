import React, { useEffect } from "react";
import axios from "axios";

export default function Stream() {
  useEffect(() => {
    const pc = new RTCPeerConnection();

    pc.ontrack = (event) => {
      console.log("Received track", event.streams[0]);
      const video = document.getElementById("remoteVideo");
      if (video) {
        video.srcObject = event.streams[0];
        video.play().catch((err) => console.warn("Playback failed:", err));
      }
    };

    async function start() {
      // No local tracks, only receive
      const offer = await pc.createOffer({ offerToReceiveVideo: true, offerToReceiveAudio: false });
      await pc.setLocalDescription(offer);

      const res = await axios.post("http://localhost:8080/offer", { offer: pc.localDescription });
      const answer = res.data.answer;
      await pc.setRemoteDescription(answer);
    }

    start();
  }, []);

  return <video id="remoteVideo" autoPlay playsInline muted style={{ width: "100%" }}></video>;
}
