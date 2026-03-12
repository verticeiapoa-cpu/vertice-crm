# Vértice CRM

## Project Overview
CRM (Customer Relationship Manager) for Vértice Agência Digital to manage clients, sales pipeline, and financial control.

- **Technology:** Pure HTML, CSS, and vanilla JavaScript (no frameworks)
- **Storage:** Browser localStorage
- **Language:** Portuguese (Brazilian)

## Project Structure
- `index.html` - Main application file (Dashboard, Pipeline, Clients, Financial views)
- `lead-hunter.html` - Lead hunting feature page

## Features
- Dashboard with metrics (monthly revenue, active projects, receivables, total clients)
- Sales pipeline with statuses: Prospect → Proposal → Closed → Delivered
- Client registration with package, value, deadline, payment, and notes
- Financial control with monthly goal (R$ 2,800) and Excel export

## Running the Project
The app is served as a static site using Python's built-in HTTP server:
```
python3 -m http.server 5000 --bind 0.0.0.0
```

## Deployment
Configured as a static deployment with the root directory as the public directory.

## Code Patterns
- Vanilla JavaScript, no external dependencies
- Dark visual style with yellow (#f5c518) as accent color
- Portuguese naming conventions for variables and functions
- Comments in Portuguese
