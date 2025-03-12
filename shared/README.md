# Shared Directory

This directory contains shared resources used by all agent containers:

- `knowledge/`: Persistent storage for the knowledge repository
- `logs/`: Shared logs for all agents

This is mounted as a volume in all agent containers to facilitate data exchange and persistence.