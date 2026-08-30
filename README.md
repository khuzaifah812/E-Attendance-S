# UICT E-Attendance System (UICT-ESAS)

A comprehensive attendance management system for UICT with physical and online lecture support.

## Features
- Multi-role authentication (Admin, Lecturer, Coordinator, Student)
- Physical and Online lecture attendance
- GPS-based location verification for physical lectures
- Academic year and semester management
- Real-time verification codes
- Device restriction to prevent multiple attendances

## Quick Start with Docker

```bash
# Clone or download the project
cd uict-esas

# Build and start the containers
docker-compose up --build

# Access the application
# Open http://localhost:8000