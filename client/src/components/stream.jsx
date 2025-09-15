import React, { useEffect, useState } from "react";
import axios from "axios";
import SimTables from "./tables";

export default function Stream() {
  const [simData, setSimData] = useState(null);

  useEffect(() => {
    const pc = new RTCPeerConnection();

    pc.ontrack = (event) => {
      const video = document.getElementById("remoteVideo");
      if (video) {
        video.srcObject = event.streams[0];
        video.play().catch((err) => console.warn("Playback failed:", err));
      }
    };

    async function startWebRTC() {
      const offer = await pc.createOffer({ offerToReceiveVideo: true, offerToReceiveAudio: false });
      await pc.setLocalDescription(offer);

      const res = await axios.post("http://localhost:8080/offer", { offer: pc.localDescription });
      const answer = res.data.answer;
      await pc.setRemoteDescription(answer);
    }

    startWebRTC();

    // Polling sim data every 200ms
    // const interval = setInterval(async () => {
    //   try {
    //     const res = await axios.get("http://localhost:8080/meta.json");
    //     setSimData(res.data);
    //   } catch (err) {
    //     console.warn("Error fetching sim data:", err);
    //   }
    // }, 200);

    // return () => {
    //   clearInterval(interval);
    //   pc.close();
    // };
  }, []);

  return (
    <div>
      <video
        id="remoteVideo"
        autoPlay
        playsInline
        muted
        style={{ width: "50%" }}
      ></video>
      <SimTables />

      {/* <pre style={{ marginTop: "1rem", background: "#f5f5f5", padding: "10px", color: 'black' }}>
        {simData ? JSON.stringify(simData, null, 2) : "Waiting for sim data..."}
      </pre> */}
    </div>
  );
}
