# Explosive Dash

## A 2D precision platformer built with Python and Pygame. Rocket-jump off the ground, phase-dash through purple walls and reach the red goal as fast as you can. Finishing times are sent to a small Flask API that stores them in SQLite and serves a top-5 leaderboard per level.

Requirements
Python 3.8 or newer
pygame, flask, flask-cors
1. Install dependencies

pip install pygame flask flask-cors

2. Start the API (optional, needed for the leaderboard)

bashpython api.py

The API runs at http://localhost:5000. The scores.db database and its scores table are created automatically on first start. API documentation is available at http://localhost:5000/docs.

3. Start the game

In a second terminal:

python game.py

Enter your name, pick a level and play. When you reach the goal, your time is sent to the API in a background thread. If the API is not running, the game keeps working and only prints Could not save score to the console.

4. View the leaderboard

Open leaderboard.html in your browser while the API is running and choose a level from the dropdown.

Controls
Action	Key
Move	A / D or Left / Right arrows
Jump	Space / W / Up arrow (release early for a shorter jump)
Rocket jump	Left mouse click (pushes you away from the cursor, once per air time)
Phase dash	Left Shift (pass through purple walls, once per air time)
Pause / resume	Esc or P
Restart level	R
Level select	M (from pause or win screen)
Next level	N (win screen)

Rocket and dash recharge when you touch the ground.

Level format

Levels are .txt files in the levels/ folder. Every level needs exactly one S and one G.

Character	Meaning
-#	Solid wall
-P	Phase wall (thin, can be dashed through)
-S	Player start
-G	Goal
. or space	Empty

The level name shown in the menu is the file name with underscores replaced by spaces, in title case (first_steps.txt becomes First Steps). This name is also what gets stored in the leaderboard.

API endpoints

Base URL: http://localhost:5000

| Method | Endpoint | Description | Request | Response |
|---|---|---|---|---|
| `GET` | `/api/levels` | List of levels that have at least one saved score | none | `200` `["First Steps", "Level Two"]` |
| `GET` | `/api/scores?level=NAME` | Top 5 times for a level (best time per player, fastest first) | Query parameter `level` | `200` `[{"username": "anna", "time_sec": 12.34, "level": "First Steps"}]` |
| `POST` | `/api/scores` | Save a finished run | JSON body: `{"username": "anna", "level": "First Steps", "time": 12.34}` | `201` `{"status": "saved"}` or `400` `{"error": "..."}` |
| `GET` | `/docs` | Simple HTML documentation page | none | `200` HTML |

Validation on POST /api/scores:

username is trimmed and cut to 15 characters
level must not be empty
time must be a number greater than 0, otherwise the API returns 400
### Example requests

```bash
# Save a score
curl -X POST http://localhost:5000/api/scores \
  -H "Content-Type: application/json" \
  -d '{"username": "anna", "level": "First Steps", "time": 12.34}'

# Get top 5 for a level
curl "http://localhost:5000/api/scores?level=First%20Steps"

# List levels
curl http://localhost:5000/api/levels
```
## Database

SQLite file `scores.db` with one table:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key, autoincrement |
| `username` | TEXT | Required |
| `level` | TEXT | Required |
| `time_sec` | REAL | Required |
| `created_at` | TEXT | Defaults to the current timestamp |

All queries use parameterised statements (`?`) to prevent SQL injection.

## Tech stack

- Python, Pygame (game)
- Flask, Flask-CORS (API)
- SQLite (storage)
- HTML / JavaScript (leaderboard page)