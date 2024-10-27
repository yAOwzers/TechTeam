package main

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

type Metrics struct {
	TotalOps      int
	SuccessfulOps int
	FailedOps     int
	TotalTime     time.Duration
	LockTimeouts  int
}

func runStressTest(db *sql.DB, numWorkers int, opsPerWorker int) Metrics {
	var wg sync.WaitGroup
	metrics := Metrics{}
	metricsMutex := sync.Mutex{}
	startTime := time.Now()

	// Create channels for coordinating workers
	workChan := make(chan int, numWorkers)

	// Start workers
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			for j := 0; j < opsPerWorker; j++ {
				hostname := fmt.Sprintf("test%d.google.com", workerID*opsPerWorker+j)
				ip := fmt.Sprintf("192.168.1.%d", (workerID*opsPerWorker+j)%255)

				// Try to insert/update record with timeout
				err := insertWithTimeout(db, hostname, ip)

				metricsMutex.Lock()
				metrics.TotalOps++
				if err != nil {
					if err.Error() == "database is locked" {
						metrics.LockTimeouts++
					}
					metrics.FailedOps++
				} else {
					metrics.SuccessfulOps++
				}
				metricsMutex.Unlock()

				// Small delay to simulate real-world usage
				time.Sleep(time.Millisecond)
			}
		}(i)
	}

	wg.Wait()
	close(workChan)

	metrics.TotalTime = time.Since(startTime)
	return metrics
}

func insertWithTimeout(db *sql.DB, hostname, ip string) error {
	// Set a timeout for the operation
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	_, err := db.ExecContext(ctx, `
		INSERT INTO dns_records (
			hostname, 
			ip_address, 
			record_type, 
			ttl, 
			created_at, 
			expires_at
		) 
		VALUES (?, ?, 'A', 300, datetime('now'), datetime('now', '+5 minutes'))
		ON CONFLICT(hostname, record_type) 
		DO UPDATE SET 
			ip_address=excluded.ip_address,
			created_at=excluded.created_at,
			expires_at=excluded.expires_at
	`, hostname, ip)

	return err
}

func main() {
	// write ahead logging
	db, err := sql.Open("sqlite3", "dns_cache.db?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		panic(err)
	}
	defer db.Close()

	concurrencyLevels := []int{1, 5, 10, 20, 50, 100}
	opsPerWorker := 1000

	fmt.Printf("Running stress test with %d operations per worker\n", opsPerWorker)
	fmt.Printf("%-10s %-15s %-15s %-15s %-15s %-15s\n",
		"Workers",
		"Total Ops",
		"Successful",
		"Failed",
		"Lock Timeouts",
		"Duration(s)")
	fmt.Println(strings.Repeat("-", 80))

	for _, workers := range concurrencyLevels {
		metrics := runStressTest(db, workers, opsPerWorker)

		fmt.Printf("%-10d %-15d %-15d %-15d %-15d %-15.2f\n",
			workers,
			metrics.TotalOps,
			metrics.SuccessfulOps,
			metrics.FailedOps,
			metrics.LockTimeouts,
			metrics.TotalTime.Seconds())
	}
}
