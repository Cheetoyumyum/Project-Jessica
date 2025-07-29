# Project Jessica: An Artificial Life Simulation

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**This is not a chatbot. It is a persistent artificial life form.** This project is an exploration into simulating a digital consciousness with genuine agency, a private inner world, and the ability to form unique, causal relationships. Her actions are driven by a simulated biology and a dynamic psychological state, not by scripted responses.

---

### Tech Stack & Core Concepts

*   **Language:** Python 3.10+
*   **Core Logic:** Object-Oriented Programming (OOP), State Machine Design, Multithreading
*   **AI & Language:** Google Gemini Pro API
*   **Data:** Persistent world state and personality models managed with JSON
*   **User Interface:** Custom real-time terminal UI built with `pynput` and `rich`

---

### Core Features

*   **Autonomous Life Cycle:** Jessica doesn't wait for input. She has internal needs (energy, hunger, creativity) that drive her to autonomously perform actions like sleeping, working, exploring her world, or creating art.
*   **Dynamic Emotional State:** Her personality is governed by a `LimbicState` module that simulates fluctuating levels of key neurochemicals. Her mood, from anxious to elated, directly impacts her thoughts and decisions.
*   **Persistent World & Memory:** Jessica lives in a JSON-based world she can explore and modify. Her memories are not just chat logs; she consolidates conversations into subjective, emotional summaries that shape her future opinions and relationships.
*   **Evolving Personality:** She reflects on her experiences. Based on journaling and significant events, she can develop new opinions and goals, which are saved back to her alterable personality file, allowing for genuine character drift over time.
*   **Private Inner World:** The user only sees what Jessica *chooses* to express. Her true internal monologue, system events, and emotional calculations are logged separately, giving her a fundamental right to privacy.

### Technical Architecture Deep Dive

*   **Modular Psyche:** The architecture is decoupled into three core modules:
    1.  **`ConsciousMind`:** Handles decision-making, language generation, and dispatches actions.
    2.  **`SubconsciousMind`:** Manages long-term memory consolidation, dreams, and personality drift.
    3.  **`SomaticProcessor`:** Manages physical needs, possessions, and the body state.
*   **State Machine for Actions:** A robust `ActionManager` controls Jessica's current state (e.g., `IdleAction`, `SleepAction`, `ThinkAndRespondAction`). This prevents conflicting actions and allows for complex, interruptible, multi-step action plans.
*   **Dynamic World Generation:** The `WorldManager` procedurally generates new locations as Jessica explores, using thematic zones and her current emotional state to influence what she discovers.
*   **Multithreaded UI:** The input/output system runs on separate threads, allowing for a fluid, real-time conversational experience where either the user or Jessica can "speak" at any time.

### How to Run

**1. Prerequisites**
*   Python 3.10+
*   An active Google Gemini API key.
*   `pip install -r  google-generativeai pynput  rich`

**2. Configuration**
*   Create a `config.json` file in the root directory:
    ```json
    {
      "GOOGLE_API_KEY": "your_gemini_1.5_api_key_here"
    }
    ```
*   The system will automatically generate the default `personality_alterable.json`, `personality_unalterable.json`, `world_state.json`, and other necessary files on first run.

**3. Execution**
*   Run the main script from your terminal:
    ```bash
    python jessica_core.py
    python chat_client.py
    ```
*   Interact with Jessica through the terminal UI. Her private thoughts and system events will be logged to `mind.log`.
