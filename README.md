# 🎓 AcademiaAI — AI-Powered Student Analytics and Success Platform

**Turning student data into meaningful insights for better academic outcomes.**

AcademiaAI is an AI-powered student analytics platform designed to help educational institutions understand student performance, identify learning challenges, monitor engagement, and improve placement readiness.

The platform brings academic records, attendance, learning activity, student engagement, skills, feedback, and placement information together in one dashboard. It helps faculty and administrators identify students who may need additional support and take action using data-driven insights.

🔗 **Live Demo:** https://academia-ai-ten.vercel.app  
🔗 **Backend API:** https://academiaai-api.onrender.com  
🔗 **GitHub Repository:** https://github.com/seerakirankumar/AcademiaAi

---

## 📌 Table of Contents

- [Project Overview](#-project-overview)
- [Problem Statement](#-problem-statement)
- [Our Solution](#-our-solution)
- [Key Features](#-key-features)
- [AI Integration](#-ai-integration)
- [How It Works](#-how-it-works)
- [Technology Stack](#-technology-stack)
- [System Architecture](#-system-architecture)
- [Dataset Information](#-dataset-information)
- [Project Structure](#-project-structure)
- [Installation and Setup](#-installation-and-setup)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [Security](#-security)
- [Future Enhancements](#-future-enhancements)
- [Disclaimer](#-disclaimer)
- [Author](#-author)

---

## 🚀 Project Overview

Educational institutions collect a large amount of student data, but understanding that data and identifying students who need support can be difficult.

AcademiaAI provides a centralized platform that transforms student information into understandable analytics, performance indicators, risk alerts, and support recommendations.

The goal is simple: **identify challenges early, support students effectively, and help institutions make better-informed decisions.**

## ❗ Problem Statement

Traditional student monitoring often focuses mainly on examination marks and attendance. This may overlook other important factors, such as:

- Learning management system (LMS) activity.
- Assignment completion and learning hours.
- Participation in events and extracurricular activities.
- Technical and soft skills.
- Placement preparation and interview performance.
- Student feedback and requests for support.

Without a unified view, it can be difficult for faculty to identify patterns and provide timely support.

## 💡 Our Solution

AcademiaAI combines student information from multiple datasets into one analytics platform.

It helps institutions:

- Understand student performance through interactive dashboards.
- Identify students who may benefit from academic or placement support.
- Examine the factors contributing to performance indicators.
- Generate rule-based recommendations for supportive interventions.
- Explore analytics through an AI-powered chat interface.
- Organize student support and intervention records.

---

## ✨ Key Features

### 1. 📊 Student Analytics Dashboard

A centralized dashboard that presents important student performance indicators and institutional analytics.

- Student population overview.
- Academic performance and CGPA analysis.
- Attendance and assignment completion insights.
- Learning activity and student engagement metrics.
- Placement readiness and skill indicators.
- Visual charts and summaries for easier understanding.

### 2. 🎯 Student Success Score

The platform calculates a student success score on a scale of 0–100 using configured performance indicators.

The preliminary scoring configuration considers:

- Academic performance — 40%.
- Attendance — 20%.
- LMS activity — 15%.
- Placement readiness — 25%.

The platform handles missing inputs by reweighting the available components when sufficient information exists. If the available data is insufficient, it avoids producing a misleading score.

**Note:** These weights are preliminary prototype assumptions and should be validated by faculty before real-world use.

### 3. 🚦 Student Risk Indicators

The platform uses
