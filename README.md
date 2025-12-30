   # 🚦 Intelligent Traffic Management System (ITMS)

An AI-powered system designed to reduce traffic congestion and improve road safety through real-time violation detection, adaptive traffic signals, and driver scoring.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Current Progress](#-current-progress)
- [Prerequisites](#-prerequisites)
- [Setup Instructions](#-setup-instructions)
  - [Step 1: Backend Setup](#step-1-backend-setup)
  - [Step 2: Frontend Setup (Web)](#step-2-frontend-setup-web)
  - [Step 3: Mobile App Setup (Optional)](#step-3-mobile-app-setup-optional)
- [Running the System](#-running-the-system)
- [Troubleshooting](#-troubleshooting)
- [Team Members](#-team-members)

---

## 🎯 Overview

**Version:** 1.0 (First Evaluation)  
**Date:** January 3, 2026  

This project demonstrates an intelligent traffic management system with:
- Real-time vehicle detection using YOLOv8
- License plate recognition with custom-trained models
- Parking and speeding violation detection
- Driver scoring system (LiveSafe Score)
- Adaptive traffic signals using fuzzy logic
- Admin dashboard for monitoring

---

## 📊 Current Progress

### ✅ Completed (Backend)

| Feature | Description | Status |
|---------|-------------|--------|
| 🚗 Vehicle Detection | YOLOv8n with DeepSORT tracking | ✅ Complete |
| 🔍 License Plate Detection | Custom YOLOv8 model (281 Sri Lankan plates) | ✅ Complete |
| 📝 OCR Integration | EasyOCR with preprocessing pipeline | ✅ Complete |
| 🅿️ Parking Violations | No-parking zone monitoring with warnings | ✅ Complete |
| ⚡ Speed Detection | Real-time speed estimation | ✅ Complete |
| 📊 Driver Scoring | 100-point LiveSafe Score system | ✅ Complete |
| 🚦 Traffic Signals | Fuzzy logic adaptive timing | ✅ Complete |
| 🔊 Voice Warnings | edge-tts + pyttsx3 audio alerts | ✅ Complete |
| 🚨 Emergency Mode | Admin-triggered emergency override | ✅ Complete |

### 🔄 In Progress (Frontend)

| Feature | Description | Status |
|---------|-------------|--------|
| 📺 Live Video Feed | Real-time detection display | ✅ Complete |
| 🚦 Traffic Light Panel | 4-way signal visualization | ✅ Complete |
| 🗺️ Zone Editor | Draw no-parking zones on map | ✅ Complete |
| 🚨 Emergency Button | Trigger emergency mode | ✅ Complete |
| 📋 Violations List | View and manage violations | 🔄 In Progress |
| 👥 Drivers List | View driver scores | 🔄 In Progress |
| 📈 Analytics | Charts and trends | 🔄 In Progress |

### 🔄 In Progress (Mobile App)

| Feature | Description | Status |
