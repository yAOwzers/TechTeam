# Sqlite3 Example

This example creates a DNS cache system using python.

There is a stress test in Golang.

The system will automatically:

- Try to resolve hostnames using the most appropriate method for the platform
- Cache successful lookups
- Return cached results if they haven't expired
- Log all operations to both console and file
- Clean up expired records when requested

## Components

**DNS Cache System**

- Stores DNS records with TTL
- Handles record updates and expiration
- Uses indexes for better performance
- Implements proper record cleanup

**Stress Test**
Tests concurrent access patterns
Measures lock timeouts
Records metrics about successful and failed operations
Uses SQLite's WAL mode for better concurrency
Implements operation timeouts

## Dependencies

- Python 3.10.10 (The version I was using at time of conception)
- Go 1.19 or higher
- virtualenv

### Installing Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install requirements.txt
```

## Running the Application

Command-line interface with three commands

- `lookup`: Look up a cache a hostname
- `list`: Show all active records
- `cleanup`: Removed expired records

Main Usage

```bash
usage: main.py [-h] [--ttl TTL] {lookup,list,cleanup} [hostname]
```

Example Usage

```bash
# Lookup and cache a domain
python3 dns_cache.py lookup google.com

# Lookup with custom TTL (1 hour)
python dns_cache.py lookup google.com --ttl 3600

# List all active records
python dns_cache.py list

# Clean up expired records
python dns_cache.py cleanup
```

### Example Usage

`lookup`

```bash
python3 main.py lookup google.com                                                                                 ─╯
2024-10-27 18:30:43,374 - INFO - Cache miss for google.com
2024-10-27 18:30:43,408 - INFO - Added/Updated record for google.com: 142.250.4.101
google.com -> 142.250.4.101
```

`list`

```bash
python3 dns_cache.py list                                                                                         ─╯

Active DNS Records:
--------------------------------------------------------------------------------
Hostname                       IP Address      Expires At               
--------------------------------------------------------------------------------
google.com                     142.250.4.101   2024-10-27 18:35:43.407262
```

## Interfacing with the Sqlite3 Database

The Application creates a sqlite3 db called "dns_cache.db" if the name of the db is not changed in the main database.

To enter the sqlite database:

```bash
sqlite3 dns_cache.db

# To find the help page
sqlite> .help

# To check the schema
sqlite> .fullschema

# To check the tables available
sqlite> .tables

# To do an query of the entire table (please do not do this if the table is very large)
sqlite> SELECT * FROM dns_records;

# To exit
sqlite> .exit
```

## Troubleshooting

If VirtualEnv fails

```bash
# If venv activation fails, try:
python -m pip install --upgrade virtualenv
rm -rf venv  # or del venv on Windows
# Then recreate the virtual environment
```