<div align="center">
  <img src="https://storage.googleapis.com/gweb-developer-goog-blog-assets/images_archive/original_images/2023_solutionchallenge_blogheader_1920x1080.png" alt="Google Solution Challenge Banner" width="100%" style="border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px;" />

  <h1 align="center">🚀 SevaSetu</h1>
  <h3 align="center">AI-Powered Smart Resource Allocation Platform</h3>

  <p align="center">
    <strong>Bridging community needs with the right help using AI.</strong><br>
    <em>Let's build the future with AI.</em>
  </p>

  <p align="center">
    <a href="https://sevasetu-242a8.web.app/">
      <img src="https://img.shields.io/badge/View_Live_MVP-FF3E4D?style=for-the-badge&logo=vercel&logoColor=white" alt="Live MVP" />
    </a>
    <a href="#-tech-stack">
      <img src="https://img.shields.io/badge/Tech_Stack-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white" alt="Tech Stack" />
    </a>
    <a href="#-built-for">
      <img src="https://img.shields.io/badge/Solution_Challenge-2026-34A853?style=for-the-badge&logo=google&logoColor=white" alt="Solution Challenge" />
    </a>
  </p>
</div>

<hr style="border: 1px solid #e0e0e0; margin: 40px 0;" />

## 🌍 Overview

Are you a student developer ready to create a difference? **SevaSetu** is built for the **Google Solution Challenge 2026 India** to solve real-world humanitarian problems using Google developer technologies.

SevaSetu is an AI-driven platform that transforms **scattered community data** into **actionable intelligence** and enables **smart volunteer coordination**. It aggregates inputs from multiple sources (surveys, WhatsApp, field reports) and uses **Generative AI + Semantic Matching** to:

<div align="center">
  <table>
    <tr>
      <td align="center">🚨<br><b>Identify</b></td>
      <td align="center">🚦<br><b>Prioritize</b></td>
      <td align="center">🤝<br><b>Match</b></td>
    </tr>
    <tr>
      <td>Urgent needs in real-time.</td>
      <td>Critical situations autonomously.</td>
      <td>The right volunteers efficiently.</td>
    </tr>
  </table>
</div>

<hr style="border: 1px dashed #e0e0e0; margin: 30px 0;" />

## 🧠 Core Idea

<div align="center">
  <h3><code>Raw Data ➔ AI Intelligence ➔ Smart Allocation ➔ Real Impact</code></h3>
</div>

<hr style="border: 1px dashed #e0e0e0; margin: 30px 0;" />

## ❗ Problem Statement vs 💡 Our Solution

| The Problem 🌪️ | The Solution 🎯 |
| :--- | :--- |
| **Scattered Data:** Information siloed across social media and apps. | **Multi-source Ingestion:** Collects distress signals globally. |
| **No Prioritization:** Hard to rank urgent vs. non-urgent needs. | **AI Understanding:** Gemini extracts context & urgency. |
| **Inefficient Assignment:** Volunteers misallocated. | **Smart Matching:** Finds best volunteer via vector similarity. |
| **Lack of Visibility:** No geographical mapping. | **Real-time Dashboards:** Live heatmaps and analytics. |

<hr style="border: 1px dashed #e0e0e0; margin: 30px 0;" />

## ⚙️ Key Features

* 🔍 **Intelligent Need Extraction:** Automatically structures unstructured inputs (need, urgency, location, required skills).
* 🎯 **Smart Volunteer Matching Engine:** Matches based on Skills, Location, Availability, and Urgency.
* 📡 **Real-Time Data Aggregation:** Unifies data channels.
* 🗺️ **Hotspot Detection:** Identifies high-risk areas using DBSCAN clustering.
* 📈 **AI Insights & Prioritization:** Recommends actionable decisions to admins.
* 🔄 **Feedback Learning System:** Continuous improvement in matching accuracy.

<hr style="border: 1px solid #e0e0e0; margin: 40px 0;" />

## 🏗️ Architecture Diagram

```mermaid
graph TD
    %% Styling Configuration
    classDef primary fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px,color:#0d47a1,rx:10px,ry:10px;
    classDef secondary fill:#e8f5e9,stroke:#43a047,stroke-width:2px,color:#1b5e20,rx:10px,ry:10px;
    classDef ai fill:#fff3e0,stroke:#fb8c00,stroke-width:2px,color:#e65100,rx:10px,ry:10px;
    classDef db fill:#fce4ec,stroke:#d81b60,stroke-width:2px,color:#880e4f,rx:10px,ry:10px;

    %% Data Sources
    subgraph "📡 Data Sources"
        S1[📋 Surveys & Forms] --> DI[📥 Data Ingestion]
        S2[💬 WhatsApp / SMS] --> DI
        S3[📝 Field Reports] --> DI
    end

    %% Backend Layer
    subgraph "⚙️ Backend Processing"
        DI --> API[🚀 FastAPI Endpoints]
        API --> NLP[🧠 NLP Processing]
    end

    %% AI Intelligence Layer
    subgraph "🤖 AI Layer"
        NLP --> GenAI[✨ Google Gemini GenAI]
        NLP --> Emb[📊 Sentence Transformers]
    end

    %% Storage Layer
    subgraph "🗄️ Database & Storage"
        GenAI --> DB[(🐘 PostgreSQL)]
        Emb --> Vec[(📈 pgvector)]
    end

    %% Core Engine
    subgraph "⚡ Core Processing Engine"
        DB --> CE[🎯 Smart Matching Engine]
        Vec --> CE
        DB --> Cluster[🗺️ DBSCAN Clustering]
        Cluster --> HD[🔥 Hotspot Detection]
    end

    %% Delivery Layer
    subgraph "💻 Delivery / UI"
        CE --> UI[🖥️ Next.js Dashboard]
        HD --> UI
        UI --> Vol[👥 Volunteers & Admins]
    end

    %% Apply Styles
    class API,DI,NLP,CE,HD primary;
    class UI,Vol secondary;
    class GenAI,Emb ai;
    class DB,Vec db;
```

<hr style="border: 1px dashed #e0e0e0; margin: 30px 0;" />

## 🔄 Process Flow

```mermaid
sequenceDiagram
    autonumber
    
    actor User as 🧑‍🤝‍🧑 Community
    participant API as ⚙️ FastAPI
    participant AI as 🧠 Gemini & AI
    participant DB as 🗄️ PostgreSQL
    participant Engine as 🚀 Match Engine
    participant UI as 💻 Dashboard

    Note over User,UI: End-to-End Need Fulfillment Pipeline

    User->>+API: Submits Need (Text/Audio)
    API->>+AI: Extract intent & urgency
    AI-->>-API: Structured Data (Urgency, Skills, Location)
    
    API->>+AI: Generate text embeddings
    AI-->>-API: Vector Representation
    
    API->>DB: Store Entity & Vector Data
    API->>+Engine: Trigger Matchmaking
    Engine->>DB: Query Nearest/Best Volunteers (pgvector)
    DB-->>Engine: Top Matched Volunteers
    
    Engine-->>-UI: Send Real-Time Updates & Matches
    UI->>User: Display Match & Notify Volunteer
```

<hr style="border: 1px solid #e0e0e0; margin: 40px 0;" />

## 🧪 Tech Stack

<div align="center">
  
| 🧠 AI / ML | ⚙️ Backend | 🗄️ Database | 🌐 Frontend |
| :---: | :---: | :---: | :---: |
| ![Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=flat-square&logo=googlebard&logoColor=white) <br> ![Transformers](https://img.shields.io/badge/Sentence%20Transformers-FF9900?style=flat-square&logo=huggingface&logoColor=white) | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) <br> ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat-square&logo=postgresql&logoColor=white) <br> ![pgvector](https://img.shields.io/badge/pgvector-336791?style=flat-square&logo=postgresql&logoColor=white) | ![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=next.js&logoColor=white) <br> ![Tailwind](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white) |

</div>

<hr style="border: 1px dashed #e0e0e0; margin: 30px 0;" />

## 🎯 Unique Selling Proposition (USP)

<details>
<summary><b>Click to reveal what makes SevaSetu unique!</b></summary>
<br>

* 🤖 **Data-driven Resource Allocation:** Completely autonomous and AI-powered.
* 🗣️ **Multilingual AI Understanding:** Breaks language barriers using Gemini.
* 📏 **Smart Multi-factor Matching:** Looks at location, skills, and urgency simultaneously.
* 🚨 **Real-time Crisis Detection:** Proactive clustering of distress signals.
* 🔎 **Explainable AI Decisions:** Transparent reasons for why a volunteer was chosen.

</details>

<hr style="border: 1px dashed #e0e0e0; margin: 30px 0;" />

## 🔮 Future Scope

* 🔮 **Predictive Crisis Detection:** Using historical data to predict outbreaks or shortages.
* 📱 **Social Media Integration:** Real-time tweet and post scraping for distress signals.
* 🏛️ **Government-level Deployment:** Scaling up for disaster management agencies.
* 🎁 **Personalized Volunteer Recommendations:** Gamified rewards based on AI history.

<hr style="border: 1px solid #e0e0e0; margin: 40px 0;" />

## 👥 Meet the Developers

Proudly built by:
* 👨‍💻 **Er. Ujjwal Chaudhary**
* 👨‍💻 **Er. Ayush Gourav**

<hr style="border: 1px solid #e0e0e0; margin: 40px 0;" />

<div align="center">
  <h2>🏆 Built For</h2>
  <img src="https://img.shields.io/badge/Google_Solution_Challenge-2026-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google Solution Challenge 2026" />
  <p><em>Build with AI — Let's build the future with AI.</em></p>
  
  <br>
  
  <h3><strong>“From scattered data to intelligent humanitarian action.”</strong></h3>
</div>
