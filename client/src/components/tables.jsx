import React, { useEffect, useState } from "react";
import axios from "axios";

// Maps Python direction labels
const DIRECTION_LABELS = { 0: "W", 1: "N", 2: "E", 3: "S" };
const DIRECTION_LABELS_1 = {
    'up': 'South',
    'down': 'North',
    'left': 'East',
    'right': 'West'
}

export default function SimTables() {
  const [simData, setSimData] = useState(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get("http://localhost:8080/meta.json");
        setSimData(res.data);
      } catch (err) {
        console.error("Failed to fetch sim data:", err);
      }
    }, 200); // poll every 200ms

    return () => clearInterval(interval);
  }, []);

  if (!simData) return <div>Loading simulation data...</div>;

  const { lane_state, signal_state, time_elapsed, current_green, current_yellow, simultaneous_green } = simData;

  return (
    <div style={{ display: "flex", gap: "50px", padding: "20px" }}>
      {/* Lane State Table */}
      <table border="1" cellPadding="5">
        <thead>
          <tr>
            <th>Direction</th>
            <th>Spawned</th>
            <th>Crossed</th>
            <th>Remaining</th>
          </tr>
        </thead>
        <tbody>
          {Object.keys(lane_state).map((dir) => (
            <tr key={dir}>
              <td>{lane_state[dir].label}</td>
              <td>{lane_state[dir].spawned}</td>
              <td>{lane_state[dir].crossed}</td>
              <td>{lane_state[dir].remaining}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Signals Table */}
      <table border="1" cellPadding="5">
        <thead>
          <tr>
            <th>Direction</th>
            <th>Status</th>
            <th>Green Duration</th>
            <th>Countdown</th>
          </tr>
        </thead>
        <tbody>
          {signal_state.map((sig, i) => {
            let status = "RED";
            let countdown = sig.red;
            if (i === current_green) {
              status = current_yellow ? "YELLOW" : "GREEN";
              countdown = current_yellow ? sig.yellow : sig.green;
            } else if (i === simultaneous_green) {
              status = current_yellow ? "YELLOW-LEFT" : "GREEN-LEFT";
              countdown = current_yellow ? sig.yellow : sig.green;
            }
            return (
              <tr key={i}>
                <td>{DIRECTION_LABELS[i]}</td>
                <td>{status}</td>
                <td>{sig.green}</td>
                <td>{countdown}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Summary Table */}
      <table border="1" cellPadding="5">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Time (s)</td>
            <td>{time_elapsed}</td>
          </tr>
          <tr>
            <td>Crossed (v)</td>
            <td>{Object.values(lane_state).reduce((acc, d) => acc + d.crossed, 0)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
