import sqlite3
import subprocess
import argparse
import socket
import platform
import re
from datetime import datetime, timedelta
import sys
import logging


class DNSResolver:
    @staticmethod
    def resolve_windows(hostname):
        try:
            output = subprocess.check_output(["nslookup", hostname], text=True)
            # Extract IP address from nslookup output
            matches = re.findall(r"Address:\s*(\d+\.\d+\.\d+\.\d+)", output)
            return matches[0] if matches else None
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def resolve_unix(hostname):
        try:
            output = subprocess.check_output(["dig", "+short", hostname], text=True)
            ips = output.strip().split("\n")
            # Return the first IPv4 address found
            for ip in ips:
                if re.match(r"\d+\.\d+\.\d+\.\d+", ip):
                    return ip
            return None
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def resolve_socket(hostname):
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            return None

    @classmethod
    def resolve(cls, hostname):
        # Try socket first (cross-platform and usually fastest)
        ip = cls.resolve_socket(hostname)
        if ip:
            return ip

        # Fall back to platform-specific tools
        if platform.system() == "Windows":
            return cls.resolve_windows(hostname)
        else:
            return cls.resolve_unix(hostname)


class DNSCache:
    def __init__(self, db_path="dns_cache.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.setup_logging()
        self.setup_database()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("dns_cache.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def setup_database(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dns_records (
                    id INTEGER PRIMARY KEY,
                    hostname TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    ttl INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    UNIQUE(hostname, record_type)
                )
            """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_hostname_type 
                ON dns_records(hostname, record_type)
            """
            )

    def add_record(self, hostname, ip_address, record_type="A", ttl=300):
        """Add or update a DNS record"""
        current_time = datetime.now()
        expires_at = current_time + timedelta(seconds=ttl)

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO dns_records 
                (hostname, ip_address, record_type, ttl, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(hostname, record_type) 
                DO UPDATE SET 
                    ip_address=excluded.ip_address,
                    ttl=excluded.ttl,
                    created_at=excluded.created_at,
                    expires_at=excluded.expires_at
            """,
                (hostname, ip_address, record_type, ttl, current_time, expires_at),
            )

        self.logger.info(f"Added/Updated record for {hostname}: {ip_address}")

    def get_record(self, hostname, record_type="A"):
        """Retrieve a DNS record if it exists and hasn't expired"""
        with self.conn:
            result = self.conn.execute(
                """
                SELECT ip_address, expires_at 
                FROM dns_records 
                WHERE hostname = ? 
                AND record_type = ?
                AND expires_at > ?
            """,
                (hostname, record_type, datetime.now()),
            ).fetchone()

            if result:
                self.logger.info(f"Cache hit for {hostname}: {result[0]}")
                return {"ip_address": result[0], "expires_at": result[1]}
            self.logger.info(f"Cache miss for {hostname}")
            return None

    def lookup_and_cache(self, hostname, ttl=300):
        """Lookup DNS and cache the result"""
        # Check cache first
        cached = self.get_record(hostname)
        if cached:
            return cached["ip_address"]

        # If not in cache, resolve
        ip = DNSResolver.resolve(hostname)
        if ip:
            self.add_record(hostname, ip, "A", ttl)
            return ip

        self.logger.warning(f"Failed to resolve {hostname}")
        return None

    def list_records(self):
        """List all non-expired records"""
        with self.conn:
            records = self.conn.execute(
                """
                SELECT hostname, ip_address, record_type, 
                       ttl, created_at, expires_at 
                FROM dns_records 
                WHERE expires_at > ?
                ORDER BY hostname
            """,
                (datetime.now(),),
            ).fetchall()

            return records

    def cleanup_expired(self):
        """Remove expired records"""
        with self.conn:
            result = self.conn.execute(
                """
                DELETE FROM dns_records 
                WHERE expires_at < ?
            """,
                (datetime.now(),),
            )
            if result.rowcount > 0:
                self.logger.info(f"Cleaned up {result.rowcount} expired records")

    def close(self):
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="DNS Cache CLI")
    parser.add_argument("command", choices=["lookup", "list", "cleanup"])
    parser.add_argument("hostname", nargs="?", help="Hostname to lookup")
    parser.add_argument("--ttl", type=int, default=300, help="TTL in seconds")
    args = parser.parse_args()

    cache = DNSCache()

    try:
        if args.command == "lookup":
            if not args.hostname:
                print("Error: hostname required for lookup")
                return
            ip = cache.lookup_and_cache(args.hostname, args.ttl)
            if ip:
                print(f"{args.hostname} -> {ip}")
            else:
                print(f"Failed to resolve {args.hostname}")

        elif args.command == "list":
            records = cache.list_records()
            if not records:
                print("No active records found")
                return
            print("\nActive DNS Records:")
            print("-" * 80)
            print(f"{'Hostname':<30} {'IP Address':<15} {'Expires At':<25}")
            print("-" * 80)
            for record in records:
                print(f"{record[0]:<30} {record[1]:<15} {record[5]}")

        elif args.command == "cleanup":
            cache.cleanup_expired()
            print("Cleanup completed")

    finally:
        cache.close()


if __name__ == "__main__":
    main()
