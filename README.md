# 🚦 Smart Traffic Management System

<p align="center">
  <img src="https://img.shields.io/badge/AI-Computer%20Vision-brightgreen?style=for-the-badge&logo=tensorflow" />
  <img src="https://img.shields.io/badge/Backend-FastAPI-blue?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Database-MongoDB-green?style=for-the-badge&logo=mongodb" />
  <img src="https://img.shields.io/badge/Dashboard-React.js-61DAFB?style=for-the-badge&logo=react" />
  <img src="https://img.shields.io/badge/Simulation-SUMO-orange?style=for-the-badge" />
</p>

---

## 📌 Description
The **Smart Traffic Management System** is a production-level AI solution designed to **optimize urban traffic flow**.  
It combines **computer vision, reinforcement learning, and real-time analytics** to dynamically adjust traffic signal timings, reduce congestion, and enhance road safety.  
The system integrates seamlessly with existing CCTV and IoT infrastructure while offering a **modern dashboard** for traffic authorities.

---

## ✨ Features
- 🔍 **Vehicle Detection & Counting:** Real-time object detection with YOLOv5 + OpenCV.  
- 🚦 **Adaptive Signal Control:** Reinforcement Learning (PPO agent) with collision-free signal phase design.  
- 📊 **Live Dashboard:** React.js dashboard to monitor traffic density, signals, and system performance.  
- 🚑 **Priority Overrides:** Emergency vehicle detection and pedestrian safety integration.  
- 🗄 **Traffic Data Storage:** MongoDB to log signals, vehicle counts, and historical patterns.  
- 🌆 **Scalable Design:** Built to extend from single intersections to multi-junction networks.  

---

## ✅ Pros
- ⚡ **Reduced Congestion:** Cuts average commute time by ~10% in simulation.  
- 🛡 **Safety-First Design:** Collision-free phase scheduling ensures safe intersections.  
- 📡 **Real-Time Monitoring:** Centralized dashboard for authorities to track live traffic conditions.  
- 🔗 **Easy Integration:** Works with existing traffic cameras and IoT devices.  
- 📈 **Data-Driven:** Historical insights for better urban planning.  

---

## ⚠️ Cons
- 🖥 **High Processing Power:** Real-time computer vision requires GPU/edge acceleration.  
- 🔧 **Training Effort:** RL agent needs substantial training data for complex intersections.  
- 📶 **Infrastructure Dependent:** Performance depends on CCTV/IoT network reliability.  

---

## 🏗 Tech Stack
| Layer                | Technology |
|----------------------|------------|
| **Backend**          | FastAPI (Python) |
| **Database**         | MongoDB |
| **Computer Vision**  | YOLOv8, OpenCV, DeepSORT |
| **Reinforcement Learning** | Stable-Baselines3 (PPO), SUMO |
| **Frontend**         | React.js + TailwindCSS |
| **API**              | REST (JSON) |

---

<p align="center">
  Built with ❤️ to make cities smarter and safer 🌆
</p>
